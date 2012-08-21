import cPickle
import urllib2
import os
from django.utils import simplejson as json

from urlparse import urljoin
from BeautifulSoup import *
from porter_stem import *

from google.appengine.ext import db
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp import template
from google.appengine.api import memcache


#some words that are ignored, these are words that add very little or no meaning. Real search engine would have many more words.
stopwords=set(['the','of','to','and','a','in','is','it'])
#page to start the crawler from 
seed_page = 'http://aaronshawpro.appspot.com/'
#imported library that cuts off suffixes that add no real extra meaning from English words 
stemmer=PorterStemmer()


class Search_Index(db.Model):
  """Storing the index in the datastore here.  All of these just stored as Text"""
  #inverted index consists of words mapping to an array of url 'ids' that contain the word
  inverted_index = db.TextProperty(required=True)
  #an array of url strings, inverted_index url id will be the index of the url  
  urls = db.TextProperty(required=True)
  #store full search words (not stemmed) for autocomplete functionality
  full_terms = db.TextProperty(required=False)




class Search (webapp.RequestHandler):
	def get(self):
		template_values = {}
		path = os.path.join(os.path.dirname(__file__), 'search.html')
		self.response.out.write(template.render(path, template_values).replace("\n", "<br />"))

	def post(self):
		terms = self.request.get('search_terms')
		result_urls = search(terms)

		template_values = {'results' : result_urls}
		path = os.path.join(os.path.dirname(__file__), 'search.html')
		self.response.out.write(template.render(path, template_values).replace("\n", "<br />"))
		
		
def search(terms):
	#first get the index and the urls from the datastore
	
	search_index = memcache.get("index")
	if search_index is None:
		q = Search_Index.all()
		result = q.fetch(1)
		search_index = result
		if not result:
			return None
		
	result_urls = []		
	inverted_index = eval(search_index[0].inverted_index)
	urls = eval(search_index[0].urls)
	
	results = []
	#for this simple search engine example, just go through the terms and return the urls that the terms are mapped to to the user
	for term in terms.split():
		stemmed_term = stemmer.stem(term, 0, len(term) - 1).lower() 
		if stemmed_term in inverted_index:
			for r in inverted_index[stemmed_term]:
				results.append(r)
		
	if results:
		for index in range(0, len(urls)) :
			if index in results :
				result_urls.append(urls[index])
				
	return result_urls
	
	



def crawl(seed_page, max_depth): # returns index, graph of inlinks
	
	pages_to_crawl = [seed_page]
	pages_to_crawl_depth = {}
	pages_to_crawl_depth[seed_page] = 0
	
	
	pages_crawled = []
	#inverted index is a dictionary with a token mapping to a list of URL id's - which is the index within the urls list that the actual url string is stored.
	inverted_index = {} 
	urls = []
	link_graph = {}  # <url>, [list of pages it links to]
	page = {}
	#full_terms are the unstemmed initial tokens (words).  Storing these just so that I can add an 'autocomplete' type Ajax feature
	full_terms = {}

	
	while pages_to_crawl:
		#get the first page that is in the list
		page = pages_to_crawl[0]
		current_depth = pages_to_crawl_depth[page]
		c = urllib2.urlopen(page)
		#using beautiful soup library to parse the html doc
		soup=BeautifulSoup(c.read())
		#only interested in tokens that are visible to the user who is browsing a page through their browser.
		soup_content = filter(visible, soup(text=True))
			
		tokens = [token.lower() for s in soup_content for token in s.split() if token not in stopwords]
		
		#place the tokens (words) for the page into the inverted index
		#append the url string into the urls list
		
		for token in tokens:
		
			stemmed_token = stemmer.stem(token, 0, len(token) - 1)
			#store url string in its own array
			if page not in urls:
				urls.append(page)
				page_index = len(urls)-1
			else:
				page_index = urls.index(page)
				
			#creat the inverted index that maps words to urls
			if stemmed_token in inverted_index and page_index not in inverted_index[stemmed_token]:
				inverted_index[stemmed_token].append(page_index)
			else:
				inverted_index[stemmed_token] = [page_index]
			#add the unstemmed terms to another dictionary (just for autocomplete functionality
			if token[0] in full_terms :
				if token not in full_terms[token[0]]:
					full_terms[token[0]].append(token)
			else :
				full_terms[token[0]] = [token]
					
				

		if current_depth < max_depth :		
			links = [link.get("href") for link in soup.findAll('a',href=True) if link.get("href").startswith("http://")]
			#keep in graph for ranking
			link_graph[page] = links
			
			for link in links:
				if link not in pages_to_crawl and link not in pages_crawled:
					pages_to_crawl.append(link)
					pages_to_crawl_depth[link] = current_depth + 1
		
		pages_crawled.append(page)
		pages_to_crawl.pop(0)
		
		#delete any index allready in datastore

		db.delete(Search_Index.all())
		
		newIndex = Search_Index(inverted_index = str(inverted_index), urls = str(urls), full_terms = str(full_terms))
		newIndex.put()

	
				
	
	
		
#we only want the text visible in the browser to be indexed
def visible(element):
    if element.parent.name in ['style', 'script', '[document]', 'head', 'title']:
        return False
    elif re.match('<!--.*-->', str(element)):
        return False
    return True
	
	
class Crawl (webapp.RequestHandler):
	def get(self):
		crawl(seed_page,2)

class Suggest (webapp.RequestHandler):
	def post(self):
		search_index = memcache.get("index")
		if search_index is None:
			q = Search_Index.all()
			result = q.fetch(1)
			search_index = result
			if not result:
				return None
			
		suggest_results = []
		
		full_terms = eval(search_index[0].full_terms)
		#get the array of terms that starts with the appropriate first letter 
		search_term = self.request.get("input")
		if search_term and search_term[0] in full_terms : 
			for term in full_terms[search_term[0]] :
				if term.startswith(search_term):
					suggest_results.append(term)

		self.response.out.write( json.dumps( {'suggestions' : suggest_results} ))

application = webapp.WSGIApplication([
  ('/search', Search),
  ('/crawl', Crawl),
  ('/suggestions', Suggest)
], debug=True)


def main():
  run_wsgi_app(application)


if __name__ == '__main__':
  main()
  
  
  
"""

def compute_ranks(graph, k):
    d = 0.8 # damping factor
    numloops = 10
    ranks = {}
    deeper_links = deep_link(graph,k)
    #graph = deeper_links
    #print graph
    
    npages = len(graph)
    for page in graph:
        ranks[page] = 1.0 / npages
    for i in range(0, numloops):
        newranks = {}
        for page in graph:
            newrank = (1 - d) / npages
            for node in graph:
                if page in graph[node] and node != page and page in deeper_links[node]:
                    newrank = newrank + d * (ranks[node]/len(graph[node]))
            newranks[page] = newrank
        ranks = newranks
    return ranks


#recursively goes through all the links withing the original graph to a depth of k and builds a new graph.  If a -> b ->c where -> is a link, and k is 2.  Then for 'a' in 
#the new graph the links will include b and c
def deep_link(graph,k):
    links = {}
    level = 0
    #need to initialise
    for page in graph:
        links[page] = []
    for page in graph:
        orig = page
        go_deeper(page, orig, links, level+1, k, graph)
        #links[page] = list(set(links[page]))
    if k == 0:
        for p in links:
            if p in links[p]:
                links[p].remove(p)
    else:
        for p in links:
            for n in links:
                if n in links[p] and p in links[n]:
                    links[p].remove(n)
                    if p in links[n]:
                        links[n].remove(p)
    
    return links

def go_deeper(page, orig, links, level, maxlevel, graph):
    
    for l in graph[page]:
        
        if l not in links[orig]:
            links[orig].append(l)
            
    for link in graph[page]:
        if level < maxlevel:
            
            go_deeper(link, orig, links,level+1,maxlevel, graph)

"""