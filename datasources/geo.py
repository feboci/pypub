import re
import time
import EUtils
from EUtils import HistoryClient, ThinClient
import urllib2
from BeautifulSoup import BeautifulSoup, BeautifulStoneSoup
from utils.cache import TimedCache
from datasources import fieldname, datasourcesError
from datasources.pubmed import filter_pmids
from datasources import ochsner, DataSource, GEO_ACCESSION_PATTERN, GEO_PLATFORM_PATTERN, PMID_PATTERN
from datasources import urlopener

#http://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE10913

EMAIL_CONTACT = "hpiwowar@gmail.com"
VERBOSE = False

class GEO(DataSource):
    
    def __init__(self, ids=[]):
        self._geo_soups = {}
        super(GEO, self).__init__(ids, "geo")

    @fieldname("geo_accession")
    def accession_number(self, id):
        return(id)

    @fieldname("geo_pmids_from_links_in_ochsner_set")
    def pmids_from_links_in_ochsner_set(self, id):
        pmids = self.pmids_from_links(id)
        ochsner_pmids = ochsner.Ochsner().all_pmids()
        pmids_in_ochsner = set(ochsner_pmids).intersection(pmids)
        return(list(pmids_in_ochsner))

    @fieldname("geo_pmids_from_links")
    def pmids_from_links(self, id):
        citation = self.citation(id)
        if not citation:
            pmids = []
        else:
            pmids = re.findall(PMID_PATTERN, citation)
        return(pmids)

    @fieldname("geo_pmid_from_links_or_ochsner")
    def pmid_from_links_or_ochsner(self, id):
        pmids = self.pmids_from_links_in_ochsner_set(id)
        if not pmids:
            pmids = self.pmid_from_ochsner(id)
        try:
            pmid = pmids[0]
        except IndexError:
            pmid = None
        return(pmid)

    @fieldname("geo_pmids")
    def pmids(self, id):
        pmids = self.pmids_from_links(id)
        return(pmids)
        
    def citation(self, id):
        if not id:
            return(None)
        soup = self.get_soup(id)
        soup = soup.find(text="Citation(s)")
        try:
            extracted_text = soup.findParent("tr").div.string
        except AttributeError:
            extracted_text = None
        return(extracted_text)

    @fieldname("geo_number_samples")
    def number_samples(self, id):
        if not id:
            return(None)
        soup = self._get_soup_hit(id, [re.compile('Samples \(\d+\)')])
        extracted_text = re.search("\d+", soup.string).group(0)
        return(extracted_text)
        
    @fieldname("geo_array_design")
    def array_design(self, id):
        try:
            soup = self._get_soup_hit(id, [re.compile(GEO_PLATFORM_PATTERN)])   
            platform_id = re.search(GEO_PLATFORM_PATTERN, soup.string).group(0)
            platform_title = soup.findNext("td").renderContents()
            extracted_text = platform_id + ": " + platform_title            
        except:
            extracted_text = None
        return(extracted_text)

    @fieldname("geo_release_date")
    def release_date(self, id):
        extracted_text = self.query_geo(id, ["Status"])
        if extracted_text:
            extracted_text = extracted_text.replace(u"Public on ", u"")
        else:
            extracted_text = ""
        return(extracted_text)

    @fieldname("geo_submitter")
    def submitter(self, id):
        response = self.query_geo(id, ["Contact name"])
        return(response)

    @fieldname("geo_submission_date")
    def submission_date(self, id):
        response = self.query_geo(id, ["Submission date"])
        return(response)
                        
    @fieldname("geo_species")
    def species(self, id):
        extracted_text = self.query_geo(id, ["Organism(s)"])
        if extracted_text:
            soup = BeautifulSoup(extracted_text)
            extracted_text = soup.a.string
        else:
            extracted_text = ""
        return(extracted_text)

    @fieldname("geo_contributors")
    def contributors(self, id):
        extracted_text = self.query_geo(id, ["Contributor(s)"])
        if extracted_text:
            soup = BeautifulSoup(extracted_text)
            extracted_text = [b.string for b in soup.findAll("a")]
        else:
            extracted_text = ""
        return(extracted_text)
        
    @fieldname("geo_dataset_in_ochsner")
    def in_ochsner(self, id):
        ochsner_geo_accessions = ochsner.Ochsner().all_accession_numbers("geo")
        response = id in ochsner_geo_accessions
        return(response)

    @fieldname("geo_pmid_from_ochsner")
    def pmid_from_ochsner(self, id):
        ochsner_pmid = ochsner.Ochsner().pmid_for_data_location(id)
        if ochsner_pmid:
            return([ochsner_pmid])
        else:
            return([])
            
    def query_geo(self, id, tags):
        try:
            soup = self._get_soup_hit(id, tags)   
            extracted_text = soup.findNext("td").renderContents()
        except:
            extracted_text = None
        return(extracted_text)
        
    def get_soup(self, geo_query_string):
        MAX_NUM_TRIES = 5
        
        if not geo_query_string:
            return(None)
        try:
            return(self._geo_soups[geo_query_string])
        except KeyError:
            num_tries = 0
            success = False
            getter = get_geo_page
            while (num_tries < MAX_NUM_TRIES and not success):
                raw_html = getter(geo_query_string)
                soup = BeautifulSoup(raw_html)
                # Verify we got a valid page
                try:
                    #assert(soup.find(text="Title")) 
                    success = True
                    print("Got geo page for %s" %geo_query_string)
                except:
                    print("Couldn't get page for %s.  Sleeping and will try again" %geo_query_string)
                    time.sleep(2)
                    num_tries += 1
                    getter = uncached_get_geo_page
            if not success:
                print soup.prettify()
                raise Exception("Page for %s not retrieved.  Perhaps server down or no internet connection?" %geo_query_string)
            self._geo_soups[geo_query_string] = soup
            return(soup)
        
    def _get_soup_hit(self, id, tags):
        try:
            soup = self.get_soup(id)
            for tag in tags:
                soup = soup.find(text=tag)
        except AttributeError:
            # No links found
            soup = None
        return(soup)
    

    
def map_booleans_to_flags(list_of_True_False):
    mapping = {True:'1', False:'0'}
    list_of_flags = [mapping[i] for i in list_of_True_False]
    return(list_of_flags)
    
@fieldname("has_geo_data")
def has_data_submission(query_pmids):
    """Returns a list of flags (0 or 1) indicating whether the PubMed IDs are listed as
    a citation in GEO.  
    """
    if not query_pmids:
        return([])
    filtered_pmids = filter_pmids(query_pmids, "pubmed_gds[filter]")
    pmid_passes_filter = [(pmid in filtered_pmids) for pmid in query_pmids]   
    flag_pmid_passes_filter = map_booleans_to_flags(pmid_passes_filter)
    return(flag_pmid_passes_filter)

@TimedCache(timeout_in_seconds=60*60*24*7)
def search_gds_for_ids(query_string, retmax=100000):
    eutils = get_eutils_client()
    raw_xml = eutils.esearch(query_string, db="gds", retmax=retmax).read()
    ids = re.findall("""<Id>(\d*)</Id>""", raw_xml)
    time.sleep(1/3)
    return(ids)

@TimedCache(timeout_in_seconds=60*60*24*7)
def get_geo_page(query_string):
    response = uncached_get_geo_page(query_string, urlopener)
    return(response)
    
def uncached_get_geo_page(query_string, opener=None):
    if not opener:
        opener = urllib2.build_opener()
    if not query_string:
        return(None)
    base_url = "http://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc="
    query_url = base_url + query_string
    page = opener.open(query_url).read()
    time.sleep(1/3)
    return(page)        
    
def query_geo_for_pmid(pmid):
    page = get_geo_page(pmid)
    successful_search_pattern = r"<bibliography><accession>" + pmid + r"</accession>"
    if re.search(successful_search_pattern, page):
        search_found_pmid = '1'
    else:
        search_found_pmid = '0'
    return(search_found_pmid)

def get_stripped_accession(id):
    id_int = int(id)
    if (id_int > 200000000):
        id_stripped = str(id_int - 200000000)
    else:
        id_stripped = id
    return(id_stripped)
    
    
def get_eutils_client():
    if VERBOSE:
        ThinClient.DUMP_URL = True
        #ThinClient.DUMP_RESULT = True
    else:
        ThinClient.DUMP_URL = False    
    eutils_client=EUtils.ThinClient.ThinClient(email=EMAIL_CONTACT, opener=urlopener)
    return(eutils_client)

def get_ids_from_gds(query):
    ids = search_gds_for_ids(query)
    return(ids)
    
def get_all_ids(id_type):
    ids = get_ids_from_gds(id_type + "[ETYP]")
    return(ids)

def get_all_gse():
    ids = get_all_ids("GSE")
    return(ids)

def get_all_gds():
    ids = get_all_ids("GDS")
    return(ids)
    
def get_ids_by_year(id_type, year):
    query = id_type + "[ETYP]"
    if year:
        query += " AND " + year + "[Publication Date]"
    ids = get_ids_from_gds(query)
    return(ids)

def get_gse_from_gds(gse_accession, retmax=100000):
    gse_ids = search_gds_for_ids(gse_accession + '[Accession]+AND+"gse"[Filter]')
    return(gse_ids)

def get_gds_from_gse(gds_accession, retmax=100000):
    gds_ids = search_gds_for_ids(gds_accession + '[Accession]+AND+"gds"[Filter]')
    return(gds_ids)


