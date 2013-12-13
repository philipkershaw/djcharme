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

Created on 2 Nov 2012

@author: mnagni
''' 
from django.conf import settings

from django.utils.http import urlencode
from django.http import HttpResponseRedirect

import socket
import logging
import re
import urllib
from djcharme.exception import SecurityError, MissingCookieError

DJ_SECURITY_SHAREDSECRET_ERROR = 'No SECURITY_SHAREDSECRET parameter \
is defined in the application settings.py file. \
Please define it accordingly to the used LOGIN_SERVICE'

AUTHENTICATION_COOKIE_MISSING = 'The expected cookie is missing. \
Redirect to the authentication service'

DJ_MIDDLEWARE_IP_ERROR = 'No DJ_MIDDLEWARE_IP parameter \
is defined in the application settings.py file. \
Please define it accordingly to the machine/proxy seen by the LOGIN_SERVICE'

LOGIN_SERVICE_ERROR = 'No LOGIN_SETTING parameter is defined in the \
application settings.py file. Please define a proper URL to the \
authenticating service'

LOGOUT = 'logout'
LOGIN = 'login'

LOGGER = logging.getLogger(__name__)

def auth_tkt_name():
    return getattr(settings, 'AUTH_TKT_NAME', 'auth_tkt')

def token_field_name():
    return getattr(settings, 'TOKEN_FIELD_NAME', 't')

def security_filter():
    return getattr(settings, 'DJ_SECURITY_FILTER', [])

def redirect_field_name():
    return getattr(settings, 'REDIRECT_FIELD_NAME', 'r')

def preapare_user_for_session(request, timestamp, userid, tokens, user_data):
    request.authenticated_user = {'timestamp': timestamp, \
                                     'userid': userid, \
                                     'tokens': tokens, \
                                     'user_data': user_data}
    LOGGER.debug("stored in request - userid:%s, user_data:%s" % (userid, user_data))
    request.session['accountid'] = userid

def filter_url(string, filters):
    """
        Checks a given strings against a list of strings.
        ** string ** string a url
        ** filters ** a list of strings
    """
    for ifilter in filters:
        if re.search(ifilter, string):
            return True

def is_public_url(request):
    url_fiters = getattr(settings, 'DJ_SECURITY_FILTER', [])
    
    #adds a default filter for reset password request
    reset_regexpr = '%s=[a-f0-9-]*$' % (token_field_name())
    if reset_regexpr not in security_filter(): 
        url_fiters.append(reset_regexpr)
        
    if url_fiters \
        and filter_url(_build_url(request), url_fiters):
        return True
    return False    

class SecurityMiddleware(object):
    """
        Validates if the actual user is authenticated agains a 
        given authentication service.
        Actually the middleware intercepts all the requests submitted 
        to the underlying Django application and verifies if the presence 
        or not of a valid paste cookie in the request.
    """

    def process_request(self, request): 
        pass
        '''
        #Has to process a reset password request? 
        if len(request.REQUEST.get(LOGOUT, '')) > 0:
            response = HttpResponseRedirect(_build_url(request))            
            response.delete_cookie(auth_tkt_name())
            request.session['accountid'] = None
            return response

        custom_auth = getattr(settings, 'DJ_SECURITY_AUTH_CHECK', None)
        if custom_auth:
            try:
                if custom_auth(request):
                    return
            #Cannot specify the Exception type as don't know the
            # exceptions type raised by custom_auth                  
            except Exception:
                pass
        
        #if not settings.DJ_MIDDLEWARE_IP:
        #    raise DJMiddlewareException(DJ_MIDDLEWARE_IP_ERROR)        
         
        try:
            qs = {redirect_field_name(): 
                  urllib.quote_plus((_build_url(request)))}             
            url = '%s?%s' % (login_service(), 
                             urlencode(qs))
            timestamp, userid, tokens, user_data = _is_authenticated(request)
            preapare_user_for_session(request, 
                                      timestamp, 
                                      userid, 
                                      tokens, 
                                      user_data)
            log_msg = ''
        except MissingCookieError:
            log_msg = "Missing cookie '%s'. Redirecting to %s" % (auth_tkt_name(), url)
        except SecurityError:                  
            log_msg = "Error in authentication. Redirecting to %s" % (url)
        finally: 
            if (len(log_msg) == 0 or is_public_url(request)) \
                and request.GET.get(LOGIN, None) == None:                    
                    return                     
            elif len(log_msg) > 0:
                LOGGER.info(log_msg)
                return HttpResponseRedirect(url)                           
        '''

            
    def process_response(self, request, response):
        return response 

def _build_url(request):
    hostname = request.environ.get('HTTP_HOST', socket.getfqdn())
    #hostname = socket.getfqdn()    
    new_get = request.GET.copy()

    #Removed the LOGIN request attribute as we now know we need to do a login
    new_get.pop(LOGIN, None)
    #Removed the LOGOUT request attribute as we now know we need to do a logout       
    new_get.pop(LOGOUT, None)

    #if request.META['SERVER_PORT'] != 80:
    #    hostname = "%s:%s" % (hostname, request.META['SERVER_PORT'])
    return 'http://%s%s?%s' % (hostname, 
                               request.path, 
                               urllib.urlencode(new_get))

def _is_authenticated(request):
    """
        Verifies the presence and validity of a paste cookie.
        If the cookie is not present the request is redirected 
        to the url specified in LOGIN_SERVICE
        ** Return ** a tuple containing (timestamp, userid, tokens, user_data)
        ** raise ** a DJ_SecurityException if the ticket is not valid
    """ 
    if auth_tkt_name() in request.COOKIES:
        LOGGER.debug("Found cookie '%s': %s in cookies" \
                     % (auth_tkt_name(), request.COOKIES.get(auth_tkt_name())))
        try:
            return 'Something'
        except Exception as ex:
            raise SecurityError(ex) 
    raise MissingCookieError(AUTHENTICATION_COOKIE_MISSING) 