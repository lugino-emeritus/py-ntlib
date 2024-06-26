import datetime
from types import CellType
from typing import Any
from . import *

__version__ = '0.1.11'

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

#-------------------------------------------------------

def data_to_str(data: Any) -> str:
	if isinstance(data, str):
		return data
	if isinstance(data, float):
		z = int(data)
		if z == data:
			data = z
	return str(data)

_DAY0 = datetime.datetime(1899,12,30)
def to_dtime(tday: float) -> datetime.datetime:
	return _DAY0 + datetime.timedelta(days=tday)
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
