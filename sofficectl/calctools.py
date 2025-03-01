import datetime
from types import CellType
from typing import Any
from . import *
from . import _norm_filepath, _extend_filepath

__version__ = '0.1.12'

CellIdType = str | tuple[int, int]

#-------------------------------------------------------

def _get_sheet_cell(sheet: PyUnoType, cell_id: CellIdType) -> PyUnoType:
	return sheet.getCellRangeByName(cell_id) if isinstance(cell_id, str) else \
		sheet.getCellByPosition(cell_id[1], cell_id[0])

def get_data_array(sheet: PyUnoType, start_cell: CellIdType, end_cell: CellIdType) -> tuple[tuple[Any,...],...]:
	return sheet.getCellRangeByName(start_cell + ':' + end_cell).DataArray if isinstance(start_cell, str) else \
		sheet.getCellRangeByPosition(start_cell[1], start_cell[0], end_cell[1], end_cell[0]).DataArray


class MiniSheet:
	def __init__(self, sheet: PyUnoType):
		self.sheet = sheet

	def __str__(self):
		return f'<MiniSheet {self.sheet.Name}>'

	def get_data(self, cell_id: CellIdType) -> Any:
		return _get_sheet_cell(self.sheet, cell_id).DataArray[0][0]
	def set_data(self, cell_id: CellIdType, val: Any) -> None:
		_get_sheet_cell(self.sheet, cell_id).DataArray = ((val,),)

	def get_formula(self, cell_id: CellIdType) -> str:
		return _get_sheet_cell(self.sheet, cell_id).Formula
	def set_formula(self, cell_id: CellIdType, f: str) -> None:
		_get_sheet_cell(self.sheet, cell_id).Formula = f

	def get_array(self, start_cell: CellIdType, end_cell: CellIdType) -> tuple[tuple[Any,...],...]:
		return get_data_array(self.sheet, start_cell, end_cell)

	def __getitem__(self, idx: CellType) -> Any:
		return self.sheet[idx].DataArray[0][0]
	def __setitem__(self, idx: CellType, val: Any) -> None:
		self.sheet[idx].DataArray = ((val,),)


def get_msheet_dic(model: PyUnoType) -> dict[str, MiniSheet]:
	return {s.Name: MiniSheet(s) for s in model.Sheets}


def export_pdf(model: PyUnoType, *, refresh: bool = False, path: str|None = None) -> str:
	if refresh:
		model.calculateAll()
	if not path:
		if (path := model.Location):
			path = os.path.splitext(path)[0] + '.pdf'
		else:
			raise ValueError('pdf export not possible, no file name found')
	else:
		path = _extend_filepath(path)
	args = (PropertyValue('FilterName', 0, 'calc_pdf_Export', 0),)
	model.storeToURL(path, args)
	return _norm_filepath(path)

#-------------------------------------------------------

def data_to_str(data: Any) -> str:
	if isinstance(data, str):
		return data
	if isinstance(data, float):
		z = int(data)
		if z == data:
			data = z
	return str(data)

_DAY0 = datetime.datetime(1899, 12, 30, 0, 0, 0)
def to_dtime(tday: float) -> datetime.datetime:
	# round to seconds
	return _DAY0 + datetime.timedelta(seconds=round(86400.0 * tday))
def from_dtime(tval: datetime.datetime) -> float:
	return (tval-_DAY0).total_seconds() / 86400.0


def cell_coordiante(s: str) -> tuple[int, int]:
	s = s.replace('$', '')
	i = next((i for i, k in enumerate(s) if k.isnumeric()), -1)
	if i >= 0:
		col = s[:i].upper()
		row = int(s[i:])-1
	else:
		col = s.upper()
		row = -1
	x = 0
	for k in col:
		x = 26 * x + ord(k) - 64
	return row, x-1
