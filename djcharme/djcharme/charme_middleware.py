'''
BSD Licence
Copyright (c) 2012, Science & Technology Facilities Council (STFC)
All rights reserved.

Redistribution and use in source and binary forms, with or without modification, 
are permitted provided that the following conditions are met:

    * Redistributions of source code must retain the above copyright notice, 
        this list of conditions and the following disclaimer.
    * Redistributions in binary form must reproduce the above copyright notice,
        this list of conditions and the following disclaimer in the documentation
        and/or other materials provided with the distribution.
    * Neither the name of the Science & Technology Facilities Council (STFC) 
        nor the names of its contributors may be used to endorse or promote 
        products derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" 
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, 
THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR 
PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS
BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, 
OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF 
SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE 
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

Created on 9 Jan 2012

@author: Maurizio Nagni
'''


import logging
from rdflib.plugins.stores.sparqlstore import SPARQLUpdateStore
from django.conf import settings
from django.contrib import messages
from djcharme import mm_render_to_response_error

formatter = logging.Formatter(fmt='%(name)s %(levelname)s %(asctime)s %(module)s %(message)s')
handler = logging.StreamHandler()
handler.setFormatter(formatter)
handler.setLevel(logging.DEBUG)
logging.getLogger().addHandler(handler)
#Temporary solution!!!
loggers = ('djcharme',)
for log_name in loggers:
    log = logging.getLogger(log_name)
    log.addHandler(handler)
    log.setLevel(logging.DEBUG)

LOGGING = logging.getLogger(__name__)

class CharmeMiddleware(object):
      
    __store = None  

    @classmethod      
    def __initStore(self): 
        store = SPARQLUpdateStore(queryEndpoint = getattr(settings,
                                                              'SPARQL_QUERY'),
                                update_endpoint = getattr(settings,
                                                          'SPARQL_UPDATE'), 
                                postAsEncoded=False)
        store.bind("rdf", "http://www.w3.org/1999/02/22-rdf-syntax-ns#")
        store.bind("oa", "http://www.w3.org/ns/oa#")
        store.bind("chnode", getattr(settings, 'NODE_URI', 'http://localhost'))
        CharmeMiddleware.__store = store        
      
    @classmethod
    def get_store(self, debug = False):
        if debug and CharmeMiddleware.__store is None:
            CharmeMiddleware.__initStore()
        return CharmeMiddleware.__store
      
    def process_request(self, request):          
        if not CharmeMiddleware.get_store():
            try:
                self.__initStore()
            except AttributeError, e:
                messages.add_message(request, messages.ERROR, e)
                messages.add_message(request, messages.INFO, 'Missing configuration')
                return mm_render_to_response_error(request, '503.html', 503)

    def process_response(self, request, response):                
        return response
    
    def process_exception(self, request, exception):
        print 'ERROR!'
