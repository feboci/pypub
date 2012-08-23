import os
import sys
#from sqlalchemy import create_engine, MetaData
#from sqlalchemy.orm import sessionmaker, scoped_session
import utils
from utils.urllib2cache import Urllib2CacheHandler
import urllib2

GEO_ACCESSION_PATTERN = r"\bG[A-Z]+\d+\b"
GEO_PLATFORM_PATTERN = r"\bGPL\d+\b"
ARRAYEXPRESS_ACCESSION_PATTERN = r"\b(E\-[A-Za-z0-9\-]+)\b"
PMID_PATTERN = r"\d{4,20}\b"

class datasourcesError(Exception):
    """Base class for exceptions in this module."""
    pass

SET_ECHO_ON = True  # set to True for lots of output

if __name__ == "__main__":
    this_dir = "."
else:
    module = sys.modules[__name__]
    this_dir = os.path.dirname(os.path.abspath(module.__file__))
#URL_CACHE_DIR = os.path.join(this_dir, '..', 'urlcache')
URL_CACHE_DIR = os.path.join('/tmp', 'urlcache')

# This is here because it only needs to be done once and it is slow
#urlopener = urllib2.build_opener(Urllib2CacheHandler(URL_CACHE_DIR, max_age = 0))
urlopener = urllib2.build_opener(Urllib2CacheHandler(URL_CACHE_DIR, max_age = 60*60*24*7))


class DataSource(object):
    def __init__(self, ids=[], db=None):
        self.ids = ids
        self.db = db
         
    def csv_format(self, list_of_columns):
        list_of_rows = self.transpose(list_of_columns)
        return(list_of_rows)

    def csv_write_to_file(self, file, input):
        # To make this a unittest, replace data_rows with canned data?
        from utils import csvunicode
        csvunicode.CsvUnicodeWriter(file).writerows(input)
        return(file)

    def collect_data_as_csv(self, ids, header_string):
        import StringIO 
    
        data = self.collect_data(ids, header_string)
        csv_data = csv_format(data)
    
        string_buffer = StringIO.StringIO()
        self.csv_write_to_file(string_buffer, csv_data)
        response = string_buffer.getvalue()
        string_buffer.close()
        return(response)

    def get_method(self, method_name):
        method_name = method_name.strip()
        if hasattr(self, method_name):
            method = getattr(self, method_name)
        else:
            raise datasourcesError("%s has no method %s" %(self.__class__, method_name))
        return(method)
        
    def get_for_ids(self, method, ids):
        response = [method(id) for id in ids]
        return(response)
    
    def get_for_self_ids(self, method):
        response = [method(id) for id in self.ids]
        return(response)
        
    def collect_data(self, header_string):
        list_of_values = []
        method_names = header_string.split(",")
        for method_name in method_names:
            print "method_name=", method_name
            method = self.get_method(method_name)
            #print "method", method
            #print "self.ids", self.ids
            values = self.get_for_self_ids(method)
            #print "getter_values:", values
            #print "getter.fieldname", method.fieldname
            list_of_values.append([method.fieldname] + values)
        return(list_of_values)
    
    def transpose(self, list_of_columns):
        rows = map(list, zip(*list_of_columns))
        return(rows)
        
    def collect_data_transposed(self, header_string):
        data = self.collect_data(header_string)
        transposed = self.transpose(data)
        return(transposed)


        
def fieldname(name):
    def decorator(f):
        # Do something with the target function
        f.fieldname = name
        return f
    return decorator
