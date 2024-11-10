> :warning: **WORK IN PROGRESS**: I wrote this when I only had the Sonic Pad hooked up to my E3S1P, and it worked great. But after getting a K1C (and putting Klipper on an RPi) I see it has a few bugs with up-to-date klipper versions. The comparison logic is also a bit buggy, but that can easily be fixed. Also, the comparison logic with gcode files generated from non-prusa slicers was done using gcode examples provided to me by other users in the community, as such, the versions/format might not be the most up to date either.
>
> I will fix all these bugs when I have time to do so.


# Moonraker Contrast (for gcode)

## Summary
This plugin is meant to add resources that can be used to compare the slicer settings used to generate two gcode files, and is basically a simple evolution of the [gcode_slicer_diff](https://github.com/jhyland87/gcode_slicer_diff) script I wrote, but with some very notable changes.

1. Written to be integrated into Moonraker as a simple plugin.
2. Saves the processed slicer settings to the metadata object, making viewing/comparing them in the future much easier and quicker.
3. Ability to process gcode generated by other slicers other than just PrusaSlicer.
4. Settings for  _config key aliases_ and _alias_modifiers_ which make it possible to compare similar values that are used by different slicers.
	- Example: PrusaSlicer has a `elefant_foot_compensation` option for dealing with the elephants foot which takes a positive value. In Cura, this can be done with the `xy_offset_layer_0` setting which would require a negative value. Thus, comparing the two would require inverting the numerical value (though it looks like recent versions of PS have also started calling it [Elephants foot compensation](https://help.prusa3d.com/article/elephant-foot-compensation_114487)).


#### Ok, but why?
Sometimes I would have a print that worked out flawlessly, and later I would try to re-slice something only for it to turn out like complete garbage. I ended up writing a [simple bash script](https://gist.github.com/jhyland87/faafd0f86535c7e5e89fc3a6163e4cc1) which would take two gcode file names, download then, filter out the settings and compare them. This ended up being a simple proof of concept for this moonraker plugin. The bash script only works with Prusa sliced gcode files, but if you mess with how the settings are found (different slicers use different setting headers/footers), it could easily work for other types.

## Limitations
It can be used to compare gcode settings sliced by different slicers, but this is probably a bit unreliable since not every slicer treats every setting value the same. I tried to fix this by introducing [setting aliases](https://github.com/jhyland87/moonraker-contrast/blob/main/src/components/slicers/cura_slicer.py#L23-L45) as well as [setting value modifiers](https://github.com/jhyland87/moonraker-contrast/blob/main/src/components/slicers/cura_slicer.py#L47-L50) that can be used to transform the value into a common format.

----

.. Ill fill the rest of this out later
