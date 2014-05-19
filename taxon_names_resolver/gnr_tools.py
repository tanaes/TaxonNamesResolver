#! /usr/bin/env python
## No warranty, no copyright
## Dominic John Bennett
## 16/05/2014
"""
Tools for interacting with the GNR.
"""

import contextlib
import json
import urllib, urllib2
import os

class GnrDataSources(object):
	"""GNR data sources class: extract IDs for specified data sources."""
	def __init__(self):
		url = 'http://resolver.globalnames.org/data_sources.json'
		with contextlib.closing(urllib2.urlopen(url)) as f:
			res = f.read()
		self.available = json.loads(res)

	def summary(self):
		# see what sources are available
		return [dict(id=ds['id'], title=ds['title']) for ds in self.available]

	def byName(self, names, invert = False):
		if invert:
			return [ds['id'] for ds in self.available if not ds['title'] in names]
		else:
			return [ds['id'] for ds in self.available if ds['title'] in names]
			
class GnrResolver(object):
	"""GNR resolver class: search the GNR"""
	def __init__(self, datasource = 'NCBI'):
		ds = GnrDataSources()
		self.write_counter = 1
		self.Id = ds.byName(datasource)
		self.otherIds = ds.byName(datasource, invert = True)

	def search(self, terms, prelim = True):
		"""Search terms against GNR. If prelim = False, search other datasources \
for alternative names (i.e. synonyms) with which to search main datasource. Return JSON object."""
		if prelim: # preliminary search
			res = self._resolve(terms, self.Id)
			self._write(res)
			return res
		else: # search other DSs for alt names, search DS with these
			res = self._resolve(terms, self.otherIds)
			self._write(res)
			alt_terms = self._parseNames(res)
			if len(alt_terms) == 0:
				return False
			else:
				terms = [each[1] for each in alt_terms] # unzip
				res = self._resolve(terms, self.Id)
				self._write(res)
				alt_res = self._replaceSupStrNames(res, alt_terms)
				return alt_res
	
	def _parseNames(self, jobj):
		# return a list of tuples (term, name) from second search
		# TODO(07/06/2013): record DSs used 
		alt_terms = []
		for record in jobj:
			if len(record) < 2:
				pass
			else:
				term = record['supplied_name_string']
				results = record['results']
				for result in results:
					r_name = result['canonical_form']
					if r_name == term:
						pass
					else:
						alt_terms.append((term, r_name))
		alt_terms = list(set(alt_terms))
		return alt_terms

	def _replaceSupStrNames(self, jobj, alt_terms):
		# replace sup name in jobj with original terms
		for record in jobj:
			sup_name = record['supplied_name_string']
			term = [i for i, each in enumerate(alt_terms) if each[1] == sup_name]
			# avoid the possibility of having the same term with >1 r_names
			term = alt_terms.pop(term[0])[0]
			record['supplied_name_string'] = term
		return jobj
		

	def _resolve(self, terms, ds_id):
		# Query server in chunks
		chunk_size = 100
		res = []
		lower = 0
		while lower < len(terms):
			upper = min(len(terms), lower + chunk_size)
			print 'Querying [{0}] to [{1}] of [{2}]'.format(lower, upper, len(terms))
			res.append(self._query(terms[lower:upper], ds_id))
			lower = upper
		res = [record for search in res for record in search['data']]
		return(res)		

	def _query(self, terms, data_source_ids):
		ds_ids = [str(id) for id in data_source_ids]
		terms = [urllib.quote(unicode(t).encode('utf8')) for t in terms]
		url = ('http://resolver.globalnames.org/name_resolvers.json?' + 
		'data_source_ids=' + '|'.join(ds_ids) + '&' + 
		'resolve_once=false&' + 
		'names=' + '|'.join(terms))
		with contextlib.closing(urllib2.urlopen(url)) as f:
			return json.loads(f.read())
	
	def _write(self, jobj):
		directory = os.path.join(os.getcwd(), 'resolved_names')
		filename = "{0}_raw_results.json".format(self.write_counter)
		jobj_file = os.path.join(directory, filename)
		with open(jobj_file, 'w') as outfile:
			json.dump(jobj, outfile)
		self.write_counter += 1

class GnrStore(dict):
	"""GNR store class: acts like a dictionary for GNR JSON format"""
	def __init__(self, terms):
		for term in terms:
			self[term] = []

	def add(self, jobj):
		if not isinstance(jobj, bool):
			for record in jobj:
				term = record['supplied_name_string']
				try:
					if len(record) > 1:
						self[term].extend(record['results'])
					else:
						self[term] = []
				except KeyError:
					print 'JSON object contains terms not in GnrStore'

	def replace(self, jobj):
		for record in jobj:
			term = record['supplied_name_string']
			try:
				if len(record) > 1:
					self[term] = record['results']
				else:
					self[term] = []
			except KeyError:
				print 'JSON object contains terms not in GnrStore'