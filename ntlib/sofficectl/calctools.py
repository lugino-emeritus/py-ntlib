import datetime

from .connect import connect_to

__version__ = '0.1.0'

#-------------------------------------------------------

def get_sheet_cell(sheet, cell_id):
	return sheet.getCellRangeByName(cell_id) if isinstance(cell_id, str) else \
			sheet.getCellByPosition(cell_id[1], cell_id[0])

def get_celldata(sheet, cell_id):
	return get_sheet_cell(sheet, cell_id).DataArray[0][0]
def set_celldata(sheet, cell_id, val):
	get_sheet_cell(sheet, cell_id).DataArray = ((val,),)

def get_arraydata(sheet, cell_id, end_id):
	return sheet.getCellRangeByName(cell_id + ':' + end_id).DataArray if isinstance(cell_id, str) else \
			sheet.getCellRangeByPosition(cell_id[1], cell_id[0], end_id[1], end_id[0]).DataArray


class MiniSheet:
	def __init__(self, sheet):
		self.sheet = sheet

	def get_data(self, cell_id):
		return get_celldata(self.sheet, cell_id)
	def set_data(self, cell_id, val):
		set_celldata(self.sheet, cell_id, val)

	def get_array(self, cell_id, end_id):
		return get_arraydata(self.sheet, cell_id, end_id)

	def __getitem__(self, ind):
		return self.sheet[ind].DataArray[0][0]
	def __setitem__(self, ind, val):
		self.sheet[ind].DataArray = ((val,),)


_DAY0 = datetime.datetime(1899,12,30)

def to_dtime(tday):
	return _DAY0 + datetime.timedelta(days=tday)

def from_dtime(tval):
	tdiff = tval - _DAY0
	return tdiff.days + tdiff.seconds / 86400
