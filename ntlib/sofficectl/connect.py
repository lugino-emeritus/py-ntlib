import os
import sys
import time
import uno

from ntlib.fctthread import start_app

__version__ = '0.1.3'

if sys.platform.startswith('win'):
	OFFICE_START_CMD = 'C:/Program Files/LibreOffice/program/soffice.exe'
else:
	OFFICE_START_CMD = 'libreoffice'

#-------------------------------------------------------

def _init_ctx(port=3103):
	lctx = uno.getComponentContext()  # local context
	resolver = lctx.ServiceManager.createInstanceWithContext('com.sun.star.bridge.UnoUrlResolver', lctx)
	resolve_param = f'uno:socket,host=localhost,port={port};urp;StarOffice.ComponentContext'
	try:
		ctx = resolver.resolve(resolve_param)
	except Exception:
		start_app((OFFICE_START_CMD, f'--accept=socket,host=localhost,port={port};urp;StarOffice.ServiceManager'))
		for _ in range(10):
			time.sleep(1)
			try:
				ctx = resolver.resolve(resolve_param)
				break
			except Exception as e:
				err = e
		else:
			raise err from None
	return ctx.ServiceManager.createInstanceWithContext('com.sun.star.frame.Desktop', ctx)

def _norm_filepath(path):
	if path.startswith('file:///'):
		path = path[(8 if sys.platform.startswith('win') else 7):]
	return os.path.normpath(path)

def _find_doc(ctx, title, path):
	res = []
	for m in ctx.Components:
		m_path = getattr(m, 'Location', None)
		if m_path:
			if path == _norm_filepath(m_path):
				return m
		m_title = getattr(m, 'Title', None)
		if m_title and title in m_title:
			res.append(m)
	if res:
		if len(res) == 1:
			return res[0]
		raise ValueError(f'title {title}, path {path} not unique')
	return None

#-------------------------------------------------------

def connect_to(name=''):
	ctx = _init_ctx()
	path = os.path.abspath(name)
	model = _find_doc(ctx, name, path)
	if model:
		return model
	if not os.path.isfile(path):
		raise ValueError(f'file {path} does not exist')
	start_app((OFFICE_START_CMD, path))
	for _ in range(10):
		time.sleep(1)
		model = ctx.getCurrentComponent()
		m_path = getattr(model, 'Location', None)
		if m_path and path == _norm_filepath(m_path):
			return model
	raise ConnectionError('not possible to connect to existing file')
