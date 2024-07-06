from .generic_slicer import GenericSlicer

class OrcaSlicer(GenericSlicer):
	_parse_reversed = True
	_options_start_pattern: str = "; CONFIG_BLOCK_START"
	_options_end_pattern: str = "; CONFIG_BLOCK_END"
	pass