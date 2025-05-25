"""LibreOffice python TCP bridge.

Base module to connect to a soffice model.
"""
__version__ = '0.2.4'

import os
import sys
import time
import uno
from com.sun.star.beans import PropertyValue  # requires module uno
from typing import Any, NewType
from .. import imp as ntimp
from ..fctthread import start_app

_START_CMD, _PORT = ntimp.load_config('sofficectl')

PyUnoType = NewType('PyUnoType', Any)

# -----------------------------------------------------------------------------

def _init_ctx() -> PyUnoType:
	lctx = uno.getComponentContext()  # local context
	resolver = lctx.ServiceManager.createInstanceWithContext('com.sun.star.bridge.UnoUrlResolver', lctx)
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

def _norm_filepath(path: str) -> str:
	if path.startswith('file:///'):
		path = path[(8 if sys.platform.startswith('win') else 7):]
	return os.path.normpath(path)

def _extend_filepath(path: str) -> str:
	if not path.startswith('file:///'):
		pre = 'file:///' if sys.platform.startswith('win') else 'file://'
		return pre + os.path.abspath(path)
	return path

def _find_doc(ctx: PyUnoType, title: str, path: str|None, query: str|None) -> PyUnoType|None:
	# make sure to init str query with query.lower()
	title_set = set()
	query_set = set()
	for m in ctx.Components:
		if m_path := getattr(m, 'Location', None):
			m_path = _norm_filepath(m_path)
			if path == m_path:
				return m
			elif query is not None and query in m_path.lower():
				query_set.add(m)
		if m_title := getattr(m, 'Title', None):
			if title == m_title:
				title_set.add(m)
			elif query is not None and query in m_title.lower():
				query_set.add(m)
	if title_set:
		if len(title_set) == 1:
			return title_set.pop()
	elif query_set:
		if len(query_set) == 1:
			return query_set.pop()
	else:
		return None
	raise ValueError(f'no unique document: query: {query}, title: {title}, path: {path}')

# -----------------------------------------------------------------------------

def connect(query: str = '') -> PyUnoType:
	ctx = _init_ctx()
	path = os.path.abspath(query)
	if os.path.isfile(path):
		iquery = None
	else:
		iquery = query.lower()
		path = None
	if model := _find_doc(ctx, query, path, iquery):
		return model
	if not path:
		raise ValueError(f'no document found for query {query}')
	start_app((_START_CMD, path))
	for _ in range(10):
		time.sleep(1.0)
		model = ctx.getCurrentComponent()
		# use getattr since the model may not be initialized
		if m_path := getattr(model, 'Location', None):
			if path == _norm_filepath(m_path):
				return model
	raise ConnectionError('not possible to connect to existing file')


def get_model_attributes(model) -> dict[Any, list[str]]:
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

