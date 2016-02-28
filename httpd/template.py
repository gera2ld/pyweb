#!/usr/bin/env python
# coding=utf-8
TEMPLATE = (
'<!DOCTYPE html>'
'<html>'
'<head>'
'<meta charset=utf-8>'
'<meta name=viewport content="width=device-width">'
'<title>%(title)s</title>'
'%(head)s'
'<style>'
'body{font-family:Tahoma;font-size:14px;background:#eee;color:#333;}'
'a{text-decoration:none;}'
'a:hover{text-decoration:underline;}'
'video{width:100%%;}'
'</style>'
'</head>'
'<body>'
'<h1>%(header)s</h1>'
'%(body)s'
'<hr>'
'%(footer)s'
'<center>&copy; 2014-2016 <a href=/>Gerald</a></center>'
'</body>'
'</html>')

def render(**kw):
    args = {
        'title': kw.get('title', 'Super Light HTTP Daemon'),
        'head': kw.get('head', ''),
        'header': kw.get('header') or kw.get('title', 'Super Light HTTP Daemon'),
        'body': kw.get('body', 'Hello world'),
        'footer': kw.get('footer', ''),
    }
    return TEMPLATE % args
