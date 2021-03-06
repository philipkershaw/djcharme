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
import socket
import logging
import re
import urllib
from djcharme.exception import SecurityError, MissingCookieError
from django.core.urlresolvers import reverse
from django.http.response import HttpResponse
from django.contrib.auth.models import AnonymousUser
from django.conf import settings
from provider.oauth2.models import AccessToken
from datetime import datetime, timedelta

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


def get_login_service_url():
    return reverse('login')


auth_tkt_name = lambda: getattr(settings, 'AUTH_TKT_NAME', 'auth_tkt')
token_field_name = lambda: getattr(settings, 'TOKEN_FIELD_NAME', 't')
security_filter = lambda: getattr(settings, 'SECURITY_FILTER', [])
redirect_field_name = lambda: getattr(settings, 'REDIRECT_FIELD_NAME', 'r')


def preapare_user_for_session(request, timestamp, userid, tokens, user_data):
    request.authenticated_user = {
        'timestamp': timestamp, 
        'userid': userid, 
        'tokens': tokens, 
        'user_data': user_data
    }
    LOGGER.debug("stored in request - userid:%s, user_data:%s", userid, 
                                                                user_data)
    request.session['accountid'] = userid


def filter_request(request, filters):
    """
        Checks a given strings against a list of strings.
        ** string ** string a url
        ** filters ** a list of strings
    """
    if filters is None:
        return False
    
    for ifilter in filters:
        if re.search(ifilter[0], request.path) and request.method in ifilter[1]:
            return True
        
    return False


def is_public_url(request):
    '''Test a given is public or secured - True if public'''
    url_filters = security_filter()
    
    #adds a default filter for reset password request
    reset_regexpr = '%s=[a-f0-9-]*$' % (token_field_name())
    if reset_regexpr not in url_filters: 
        url_filters.append(reset_regexpr)
        
    if filter_request(request, url_filters):
        LOGGER.debug('Public path and method %r / %r', request.path, 
                                                       request.method)
        return True
    
    LOGGER.debug('Secured path and method %r / %r', request.path, 
                                                    request.method)
    return False    


def is_valid_token(token):
    if token:
        try:
            access_t = AccessToken.objects.get(token=token)
            if datetime.now(access_t.expires.tzinfo) - access_t.expires \
                    < timedelta(seconds=0):
                return True
        except AccessToken.DoesNotExist:
            return False        
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
        LOGGER.debug('SecurityMiddleware.process_request for %r',
                     request.build_absolute_uri())
          
        #The required URL is public
        if is_public_url(request):                    
            return                     

        #The request has an Access Token
        if request.environ.get('HTTP_AUTHORIZATION', None):  
            for term in request.environ.get('HTTP_AUTHORIZATION').split():
                if is_valid_token(term):
                    return

        login_service_url = get_login_service_url()        
        
        #An anonymous user want to access restricted resources
        if request.path != login_service_url \
            and isinstance(request.user, AnonymousUser):
            return HttpResponse(login_service_url, status=401)
        
        #An anonymous user wants to login        
        if request.path == get_login_service_url():
            return
        return
            
    def process_response(self, request, response):
        if hasattr(response, 'url') and "access_token=" in response.url \
        and "token_type" in response.url:
            try:                          
                response.delete_cookie("sessionid")
                response.delete_cookie("csrftoken")
                #att_token = {'token': json.loads(response.content)}                
                #return mm_render_to_response(request, att_token, "token_response.html")                             
            except Exception as e:
                print e           
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