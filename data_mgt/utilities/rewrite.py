import time

def rewrite_collection(db, incoll, outcoll, func, batchsize=1000, reindex=True, filter=None, projection=None):
    """
    
    Pipes an existing collection to a new collection via a user specified function
    that may update records as the pass through.
    
    All indexes will be recreated (in lex order), unless reindex is set to false.
    The parameter outcoll must be the name of a collection that does not exist,
    rewrite_collection will not overwrite an existing collection.
    
    Required arguments:
    
     db: a mongo db to which the caller has write access
     
     incoll: name of an existing collection in db
     
     outcoll: name of the output collection (must not exist)
     
     func: function that takes a mongo db document (dictionary) and returns a (possibly) updated version of it
     
    Optional arguments:
 
      batchsize: number of records to process at once
      
      reindex: whether or not to recreate indexes (if false, no indexes will be created, you must create them)
      
      filter: pymongo filter string you may use to select a subset of the input records
      
      projection: pymongo filter you may use to select a subset of record attributes
 
    For collections with large records, you will likely want to specify a batchsize less than 1000
    (the total size of a batch should be less than 16MB)

    Example usage:
    
        rewrite_collection(db,"old_stuff","new_stuff",lambda x: x)

    """
    if outcoll in db.collection_names():
        print "Collection %s already exists in database %s, please drop it first" % (outcoll, db.name)
        return
    if not incoll in db.collection_names():
        print "Collection %s not found in database %s" % (incoll, db.name)
        return
    start = time.time()
    inrecs = db[incoll].find(filter, projection)
    db.create_collection(outcoll)
    outrecs = []
    incnt = 0
    outcnt = 0
    tot = inrecs.count()
    for r in inrecs:
        incnt += 1
        rec = func(r)
        if rec:
            outcnt += 1
            outrecs.append(rec)
        if len(outrecs) >= batchsize:
            db[outcoll].insert_many(outrecs)
            print "%d of %d records (%.1f percent) processed in %.3f secs" % (incnt, tot, 100.0*incnt/tot,time.time()-start)
            outrecs=[]
    if outrecs:
        db[outcoll].insert_many(outrecs)
    assert db[outcoll].count() == outcnt
    print "Inserted %d records of %d records in %.3f secs" % (outcnt, incnt, time.time()-start)
    if reindex:
        reindex_collection(db,incoll,outcoll)
    print "Rewrote %s to %s, total time %.3f secs" % (incoll, outcoll, time.time()-start)

def reindex_collection(db, incoll, outcoll):
    """
    
    Creates indexes on outcoll matching those that exist on incoll.
    Indexes are created in lexicographic order.
    
    Required arguments:
    
     db: a mongo db to which the caller has write access
     
     incoll: the name of an existing collection in db whose index information will be used
     
     outcoll: the name of an existing collection in db on which indexes will be created
    
    """
    indexes = db[incoll].index_information()
    keys = [(k,indexes[k]['key']) for k in indexes if k != '_id_']
    keys.sort() # sort indexes by keyname so (attr1) < (attr1,attr2) < (attr1,attr2,attr3) < ...
    for i in range(len(keys)):
        now = time.time()
        key = [(a[0],int(1) if a[1] > 0 else int(-1)) for a in keys[i][1]] # deal with legacy floats (1.0 vs 1)
        db[outcoll].create_index(key)
        print "created index %s in %.3f secs" % (keys[i][0], time.time()-now)

def add_counter(rec=None):
    if not rec:
        old_num = add_counter.num
        add_counter.num = 0
        return old_num
    add_counter.num += 1
    rec['num'] = int(add_counter.num)
    return rec
add_counter.num = 0

def create_random_object_index(db, coll, filter=None):
    """

    Creates (or recreates) a collection named incoll.rand used to support fast random object access.
    This index will automatically be used by the functions random_object_from_collection and
    random_value_from_collection (in lmfdb.utils) to improve performance.
    
    Required arguments:

        db: a mongo db to which the caller has write access
        
        coll: the name of an existing collection in db (string)
     
    Optional arugments:
    
     filter: pymongo filter string you may use to restrict random object access to a subset of records
    
    
    The new collection consists of records with "_id" taken from coll and a sequentially assigned "num"
    (starting at 1) with an index on num.

    """
    outcoll = coll+".rand"
    if outcoll in db.collection_names():
        print "Dropping existing collection %s in db %s" % (outcoll,db.name)
        db[outcoll].drop()
    add_counter() # reset counter
    rewrite_collection (db, coll, outcoll, add_counter, reindex=False, filter=filter, projection={'_id':True})
    db[outcoll].create_index('num')

def update_attribute_stats(db, coll, attributes):
    """
    
    Creates or updates statistic record in coll.stats for the specified attribute or list of attributes.
    The collection coll.stats will be created if it does not already exist.
    
    Required arguments:

        db: a mongo db to which the caller has write access
        
        coll: the name of an existing collection in db
        
        attributes: a string or list of strings specifying attributes whose statistics will be collected, each attribute will get its own statistics record (use update_joint_attribute_stats for joint statistics)

    Each statistics record contains a list of counts of each distinct value of the specified attribute
    NOTE: pymongo will raise an error if the size of this list exceeds 16MB

    """
    from bson.code import Code
    statscoll = coll + ".stats"
    if isinstance(attributes,basestring):
        attributes = [attributes]
    for attr in attributes:
        db[statscoll].delete_one({'_id':attr})
    total = db[coll].count()
    reducer = Code("""function(key,values){return Array.sum(values);}""")
    for attr in attributes:
        mapper = Code("""function(){emit(""+this."""+attr+""",1);}""")
        counts = sorted([ [r['_id'],int(r['value'])] for r in db[coll].inline_map_reduce(mapper,reducer)])
        min, max = counts[0][0], counts[-1][0]
        db[statscoll].insert_one({'_id':attr, 'total':total, 'counts':counts, 'min':min, 'max':max})

def update_joint_attribute_stats(db, coll, attributes):
    """
    
    Creates or updates joint statistic record in coll.stats for the specified attributes.
    The collection coll.stats will be created if it does not already exist.
    
    Required arguments:

        db: a mongo db to which the caller has write access
        
        coll: the name of an existing collection in db
        
        attributes: a list of strings specifying attributes whose joint statistics will be collected

    Each statistics record contains a list of counts of each distinct value of the specified attribute
    NOTE: pymongo will raise an error if the size of this list exceeds 16MB

    """
    from bson.code import Code
    statscoll = coll + ".stats"
    jointkey = "-".join(attributes)
    db[statscoll].delete_one({'_id':jointkey})
    total = db[coll].count()
    reducer = Code("""function(key,values){return Array.sum(values);}""")
    mapper = Code("""function(){emit(""+"""+"+"":""".join(["this."+attr for attr in attributes])+""",1);}""")
    counts = sorted([ [r['_id'],int(r['value'])] for r in db[coll].inline_map_reduce(mapper,reducer)])
    min, max = counts[0][0], counts[-1][0]
    db[statscoll].insert_one({'_id':jointkey, 'total':total, 'counts':counts, 'min':min, 'max':max})

