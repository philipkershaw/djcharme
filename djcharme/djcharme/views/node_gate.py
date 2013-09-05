'''
Created on 14 May 2013

@author: mnagni
'''
from djcharme.node.actions import OA, FORMAT_MAP, \
ANNO_SUBMITTED, insert_rdf, find_resource_by_id, RESOURCE, \
_collect_annotations, change_annotation_state, find_annotation_graph    , DATA,\
    PAGE
from djcharme import mm_render_to_response, mm_render_to_response_error
from djcharme.exception import SerializeError, StoreConnectionError
from djcharme.views import isGET, isPOST, content_type, validateMimeFormat,\
    isOPTIONS, http_accept

from django.http.response import HttpResponseRedirectBase, Http404, HttpResponse
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt, csrf_protect

import logging
import json

LOGGING = logging.getLogger(__name__)

class HttpResponseSeeOther(HttpResponseRedirectBase):
    '''
        Implements a simple HTTP 303 response
    '''
    status_code = 303

def __serialize(graph, req_format = 'application/rdf+xml'):
    '''
        Serializes a graph according to the required format
        - rdflib:Graph **graph** the graph to serialize
        - string **req_format** the serialization format
        - **return** the serialized graph                
    '''         
    if req_format == 'application/ld+json':
        req_format = 'json-ld'
    return graph.serialize(format=req_format)



def _validateFormat(request):
    '''
        Returns the mimetype of the required format as mapped by rdflib
        return: String - an allowed rdflib mimetype 
    '''
    req_format = None
    
    if isGET(request):
        if request.GET.get('format', 'html') == 'html':
            return 'html'
        req_format = FORMAT_MAP.get(request.GET.get('format', None))        
    
    if isPOST(request):
        req_format = request.environ.get('CONTENT_TYPE', None)        
    
    if req_format is None:
        raise SerializeError("Cannot generate the required format %s " % req_format)
    
    if req_format not in FORMAT_MAP.values():
        raise SerializeError("Cannot generate the required format %s " % req_format)
    
    return req_format

def index(request, graph = 'stable'):
    '''
        Returns a tabular view of the stored annotations.
        - HTTPRequest **request** the client request
        - string **graph**  the required named graph
        TDB - In a future implemenation this actions should be supported by an OpenSearch implementation
    '''
    tmp_g = None
    try:
        tmp_g = _collect_annotations(graph)
    except StoreConnectionError as e:
        messages.add_message(request, messages.ERROR, e)
        return mm_render_to_response_error(request, '503.html', 503)
        
                
    req_format = _validateFormat(request)
    
    if req_format != 'html':
        LOGGING.debug("Annotations %s" % __serialize(tmp_g, req_format = req_format))
        return HttpResponse(__serialize(tmp_g, req_format = req_format))

    states = {}            
    LOGGING.debug("Annotations %s" % tmp_g.serialize())
    for s, p, o in tmp_g.triples((None, None, OA['Annotation'])):
        states[s] = find_annotation_graph(s)   
        
    context = {'results': tmp_g.serialize(), 'states': json.dumps(states)}
    return mm_render_to_response(request, context, 'viewer.html')

# Temporary solution as long identify a solution for csrf
#@csrf_protect
@csrf_exempt  
def insert(request):
    '''
        Inserts in the triplestore a new annotation under the "ANNO_SUBMITTED" graph
    '''
    try:
        req_format = _validateFormat(request)
        
    except SerializeError as e:
        messages.add_message(request, messages.ERROR, e)
        return mm_render_to_response_error(request, '400.html', 400)
    
    if isPOST(request) or isOPTIONS(request):
        triples = request.body
        tmp_g = insert_rdf(triples, req_format, graph=ANNO_SUBMITTED) 
        ret_format = validateMimeFormat(request)
        if ret_format is None:
            ret_format = req_format
        return HttpResponse(__serialize(tmp_g, req_format = ret_format), content_type=FORMAT_MAP.get(ret_format))


# Temporary solution as long identify a solution for csrf
#@csrf_protect
@csrf_exempt         
def advance_status(request):
    '''
        Advance the status of an annotation
    '''            
    if isPOST(request) and 'application/json' in content_type(request):
        params = json.loads(request.body) 
        if not params.has_key('annotation') or not params.has_key('state'):
            messages.add_message(request, messages.ERROR, "Missing annotation/state parameters")
            return mm_render_to_response_error(request, '400.html', 400)
        LOGGING.info("advancing %s to state:%s" % (params.get('annotation'), params.get('toState')))
        tmp_g = change_annotation_state(params.get('annotation'), params.get('toState'))
        
        return HttpResponse(tmp_g.serialize())
        
        
def process_resource(request, resource_id):  
    if validateMimeFormat(request):           
        LOGGING.info("Redirecting to /%s/%s" % (DATA, resource_id))
        return HttpResponseSeeOther('/%s/%s' % (DATA, resource_id))
    if 'text/html' in http_accept(request):
        LOGGING.info("Redirecting to /%s/%s" % (PAGE, resource_id))
        return HttpResponseSeeOther('/%s/%s' % (PAGE, resource_id))
    return Http404()
        
def process_data(request, resource_id):
    if 'text/html' in http_accept(request):
        return process_resource(request, resource_id = None)
    
    req_format = validateMimeFormat(request)
    if req_format is None:
        return process_resource(request, resource_id)
            
    tmp_g = find_resource_by_id(resource_id)           
    return HttpResponse(tmp_g.serialize(format = req_format), 
                            mimetype = FORMAT_MAP.get(req_format))  

def process_page(request, resource_id = None):
    if 'text/html' not in http_accept(request):
        return process_resource(request, resource_id)
        
    tmp_g = find_resource_by_id(resource_id)                 
    context = {'results': tmp_g.serialize()}
    return mm_render_to_response(request, context, 'viewer.html')
