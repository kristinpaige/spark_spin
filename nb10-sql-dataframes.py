
# coding: utf-8

# # Spark SQL and Data Frames

# [Introduction to Spark with Python, by Jose A. Dianes](http://jadianes.github.io/spark-py-notebooks)

# This notebook will introduce Spark capabilities to deal with data in a structured way. Basically, everything turns around the concept of *Data Frame* and using *SQL language* to query them. We will see how the data frame abstraction, very popular in other data analytics ecosystems (e.g. R and Python/Pandas), it is very powerful when performing exploratory data analysis. In fact, it is very easy to express data queries when used together with the SQL language. Moreover, Spark distributes this column-based data structure transparently, in order to make the querying process as efficient as possible.      

# ## Getting the data and creating the RDD

# As we did in previous notebooks, we will use the reduced dataset (10 percent) provided for the [KDD Cup 1999](http://kdd.ics.uci.edu/databases/kddcup99/kddcup99.html), containing nearly half million nework interactions. The file is provided as a Gzip file that we will download locally.  

# In[1]:

import urllib
f = urllib.urlretrieve ("http://kdd.ics.uci.edu/databases/kddcup99/kddcup.data_10_percent.gz", "kddcup.data_10_percent.gz")


# In[2]:

data_file = "./kddcup.data_10_percent.gz"
raw_data = sc.textFile(data_file).cache()


# ## Getting a Data Frame

# A Spark `DataFrame` is a distributed collection of data organized into named columns. It is conceptually equivalent to a table in a relational database or a data frame in R or Pandas. They can be constructed from a wide array of sources such as a existing RDD in our case.

# The entry point into all SQL functionality in Spark is the `SQLContext` class. To create a basic instance, all we need is a `SparkContext` reference. Since we are running Spark in shell mode (using pySpark) we can use the global context object `sc` for this purpose.    

# In[3]:

from pyspark.sql import SQLContext
sqlContext = SQLContext(sc)


# ### Inferring the schema

# With a `SQLContext`, we are ready to create a `DataFrame` from our existing RDD. But first we need to tell Spark SQL the schema in our data.   

# Spark SQL can convert an RDD of `Row` objects to a `DataFrame`. Rows are constructed by passing a list of key/value pairs as *kwargs* to the `Row` class. The keys define the column names, and the types are inferred by looking at the first row. Therefore, it is important that there is no missing data in the first row of the RDD in order to properly infer the schema.

# In our case, we first need to split the comma separated data, and then use the information in KDD's 1999 task description to obtain the [column names](http://kdd.ics.uci.edu/databases/kddcup99/kddcup.names).  

# In[4]:

from pyspark.sql import Row

csv_data = raw_data.map(lambda l: l.split(","))
row_data = csv_data.map(lambda p: Row(
    duration=int(p[0]), 
    protocol_type=p[1],
    service=p[2],
    flag=p[3],
    src_bytes=int(p[4]),
    dst_bytes=int(p[5])
    )
)


# Once we have our RDD of `Row` we can infer and register the schema.  

# In[5]:

interactions_df = sqlContext.createDataFrame(row_data)
interactions_df.registerTempTable("interactions")


# Now we can run SQL queries over our data frame that has been registered as a table.  

# In[6]:

# Select tcp network interactions with more than 1 second duration and no transfer from destination
tcp_interactions = sqlContext.sql("""
    SELECT duration, dst_bytes FROM interactions WHERE protocol_type = 'tcp' AND duration > 1000 AND dst_bytes = 0
""")
tcp_interactions.show()


# The results of SQL queries are RDDs and support all the normal RDD operations.  

# In[7]:

# Output duration together with dst_bytes
tcp_interactions_out = tcp_interactions.map(lambda p: "Duration: {}, Dest. bytes: {}".format(p.duration, p.dst_bytes))
for ti_out in tcp_interactions_out.collect():
  print ti_out


# We can easily have a look at our data frame schema using `printSchema`.  

# In[8]:

interactions_df.printSchema()


# ## Queries as `DataFrame` operations

# Spark `DataFrame` provides a domain-specific language for structured data manipulation. This language includes methods we can concatenate in order to do selection, filtering, grouping, etc. For example, let's say we want to count how many interactions are there for each protocol type. We can proceed as follows.  

# In[9]:

from time import time

t0 = time()
interactions_df.select("protocol_type", "duration", "dst_bytes").groupBy("protocol_type").count().show()
tt = time() - t0

print "Query performed in {} seconds".format(round(tt,3))


# Now imagine that we want to count how many interactions last more than 1 second, with no data transfer from destination, grouped by protocol type. We can just add to filter calls to the previous.   

# In[10]:

t0 = time()
interactions_df.select("protocol_type", "duration", "dst_bytes").filter(interactions_df.duration>1000).filter(interactions_df.dst_bytes==0).groupBy("protocol_type").count().show()
tt = time() - t0

print "Query performed in {} seconds".format(round(tt,3))


# We can use this to perform some [exploratory data analysis](http://en.wikipedia.org/wiki/Exploratory_data_analysis). Let's count how many attack and normal interactions we have. First we need to add the label column to our data.    

# In[11]:

def get_label_type(label):
    if label!="normal.":
        return "attack"
    else:
        return "normal"
    
row_labeled_data = csv_data.map(lambda p: Row(
    duration=int(p[0]), 
    protocol_type=p[1],
    service=p[2],
    flag=p[3],
    src_bytes=int(p[4]),
    dst_bytes=int(p[5]),
    label=get_label_type(p[41])
    )
)
interactions_labeled_df = sqlContext.createDataFrame(row_labeled_data)


# This time we don't need to register the schema since we are going to use the OO query interface.  

# Let's check the previous actually works by counting attack and normal data in our data frame.  

# In[12]:

t0 = time()
interactions_labeled_df.select("label").groupBy("label").count().show()
tt = time() - t0

print "Query performed in {} seconds".format(round(tt,3))


# Now we want to count them by label and protocol type, in order to see how important the protocol type is to detect when an interaction is or not an attack.  

# In[13]:

t0 = time()
interactions_labeled_df.select("label", "protocol_type").groupBy("label", "protocol_type").count().show()
tt = time() - t0

print "Query performed in {} seconds".format(round(tt,3))


# At first sight it seems that *udp* interactions are in lower proportion between network attacks versus other protocol types.  

# And we can do much more sophisticated groupings. For example, add to the previous a "split" based on data transfer from target.   

# In[14]:

t0 = time()
interactions_labeled_df.select("label", "protocol_type", "dst_bytes").groupBy("label", "protocol_type", interactions_labeled_df.dst_bytes==0).count().show()
tt = time() - t0

print "Query performed in {} seconds".format(round(tt,3))


# We see how relevant is this new split to determine if a network interaction is an attack.  

# We will stop here, but we can see how powerful this type of queries are in order to explore our data. Actually we can replicate all the splits we saw in previous notebooks, when introducing classification trees, just by selecting, groping, and filtering our dataframe. For a more detailed (but less real-world) list of Spark's `DataFrame` operations and data sources, have a look at the official documentation [here](https://spark.apache.org/docs/latest/sql-programming-guide.html#dataframe-operations).    
