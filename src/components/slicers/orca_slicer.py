from .base_slicer import BaseSlicer

class OrcaSlicer(BaseSlicer):
	_parse_reversed = True
	_opt_start_str: str = "; CONFIG_BLOCK_START"
	_opt_end_str: str = "; CONFIG_BLOCK_END"
	pass