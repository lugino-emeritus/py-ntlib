import datetime

from .connect import *

__version__ = '0.1.5'

#-------------------------------------------------------

def get_msheet_dic(model):
	return {s.Name: MiniSheet(s) for s in model.Sheets}

def _get_sheet_cell(sheet, cell_id):
	return sheet.getCellRangeByName(cell_id) if isinstance(cell_id, str) else \
		sheet.getCellByPosition(cell_id[1], cell_id[0])

def get_celldata(sheet, cell_id):
	return _get_sheet_cell(sheet, cell_id).DataArray[0][0]
def set_celldata(sheet, cell_id, val):
	_get_sheet_cell(sheet, cell_id).DataArray = ((val,),)

def get_arraydata(sheet, start_cell, end_cell):
	return sheet.getCellRangeByName(start_cell + ':' + end_cell).DataArray if isinstance(start_cell, str) else \
		sheet.getCellRangeByPosition(start_cell[1], start_cell[0], end_cell[1], end_cell[0]).DataArray


class MiniSheet:
	def __init__(self, sheet):
		self.sheet = sheet

	def get_data(self, cell_id):
		return get_celldata(self.sheet, cell_id)
	def set_data(self, cell_id, val):
		set_celldata(self.sheet, cell_id, val)

	def get_array(self, start_cell, end_cell):
		return get_arraydata(self.sheet, start_cell, end_cell)

	def __getitem__(self, idx):
		return self.sheet[idx].DataArray[0][0]
	def __setitem__(self, idx, val):
		self.sheet[idx].DataArray = ((val,),)


def data_to_str(data):
	if isinstance(data, str):
		return data
	if isinstance(data, float):
		z = int(data)
		if z == data:
			data = z
	return str(data)

_DAY0 = datetime.datetime(1899,12,30)
def to_dtime(tday):
	return _DAY0 + datetime.timedelta(days=tday)
def from_dtime(tval):
	return (tval-_DAY0).total_seconds / 86400.0
