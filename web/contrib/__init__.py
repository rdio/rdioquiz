#!/usr/bin/env python

import wsgiref.handlers, os

def application(environ, start_response):
    start_response('200 OK', [('Content-Type', 'text/plain')])
    return [`os.environ`]

if __name__ == '__main__':
    wsgiref.handlers.CGIHandler().run(application)
