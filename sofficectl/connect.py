import os
import sys
import time
import uno

from .. import imp as ntimp
from ..fctthread import start_app

__version__ = '0.1.8'

_START_CMD, _PORT = ntimp.load_config('sofficectl')

raise RuntimeError('This module is outated, use connect from sofficectl')

#-------------------------------------------------------

def _init_ctx():
	lctx = uno.getComponentContext()  # local context
	resolver = lctx.ServiceManager.createInstance('com.sun.star.bridge.UnoUrlResolver')
	resolve_param = f'uno:socket,host=localhost,port={_PORT};urp;StarOffice.ComponentContext'
	try:
		ctx = resolver.resolve(resolve_param)
	except Exception:
		start_app((_START_CMD, f'--accept=socket,host=localhost,port={_PORT};urp;StarOffice.ServiceManager'))
		for _ in range(10):
			time.sleep(1.0)
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
		if m_path := getattr(m, 'Location', None):
			if path == _norm_filepath(m_path):
				return m
		if m_title := getattr(m, 'Title', None):
			if title == m_title:
				return m
			elif title.lower() in m_title.lower():
				res.append(m)
	if res:
		if len(res) == 1:
			return res[0]
		raise ValueError(f'title {title}, path {path} not unique')
	return None

#-------------------------------------------------------

def connect(name=''):
	ctx = _init_ctx()
	path = os.path.abspath(name)
	if model := _find_doc(ctx, name, path):
		return model
	if not os.path.isfile(path):
		raise ValueError(f'file {path} does not exist')
	start_app((_START_CMD, path))
	for _ in range(10):
		time.sleep(1.0)
		model = ctx.getCurrentComponent()
		m_path = getattr(model, 'Location', None)
		if m_path and path == _norm_filepath(m_path):
			return model
	raise ConnectionError('not possible to connect to existing file')


def get_model_attributes(model):
	keys = {}
	for x in model.__dir__():
		try:
			a = getattr(model, x)
		except Exception:
			continue
		t = type(a)
		if v := keys.get(t):
			v.add(x)
		else:
			keys[t] = {x}
	return {k: sorted(v) for k, v in keys.items()}
