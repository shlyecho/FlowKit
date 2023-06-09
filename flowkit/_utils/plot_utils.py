"""
Utility functions related to plotting
"""
import numpy as np
from scipy.interpolate import interpn
import colorsys
from matplotlib import cm, colors
from bokeh.plotting import figure
from bokeh.models import Ellipse, Patch, Span, BoxAnnotation, Rect, ColumnDataSource, Title
from .._models import gates, dimension
from .._models.gating_strategy import GatingStrategy


line_color = "#1F77B4"
line_color_contrast = "#73D587"
line_width = 3
fill_color = 'lime'
gate_fill_alpha = 0.08


def _generate_custom_colormap(colormap_sample_indices, base_colormap):
    x = np.linspace(0, np.pi, base_colormap.N)
    new_lum = (np.sin(x) * 0.75) + .25

    new_color_list = []

    for i in colormap_sample_indices:
        (r, g, b, a) = base_colormap(i)
        (h, s, v) = colorsys.rgb_to_hsv(r, g, b)

        mod_v = (v * ((196 - abs(i - 196)) / 196) + new_lum[i]) / 2.

        new_r, new_g, new_b = colorsys.hsv_to_rgb(h, 1., mod_v)
        (_, new_l, _) = colorsys.rgb_to_hls(new_r, new_g, new_b)

        new_color_list.append((new_r, new_g, new_b))

    return colors.LinearSegmentedColormap.from_list(
        'custom_' + base_colormap.name,
        new_color_list,
        256
    )


cm_sample = [
    0, 4, 8, 12, 24, 36, 48, 60, 72, 80, 92,
    100, 108, 116, 124, 132,
    139, 147, 155, 159,
    163, 167, 171, 175, 179, 183, 187, 191, 195, 199, 215, 231, 239
]

new_jet = _generate_custom_colormap(cm_sample, cm.get_cmap('jet'))


def _get_false_bounds(bool_array):
    diff = np.diff(np.hstack((0, bool_array, 0)))

    start = np.where(diff == 1)
    end = np.where(diff == -1)

    return start[0], end[0]


def plot_channel(channel_events, label, subplot_ax, xform=None, flagged_events=None):
    """
    Plots a single-channel of FCS event data with the x-axis as the event number (similar to having
    time on the x-axis, but events are equally spaced). This function takes a Matplotlib Axes object
    to enable embedding multiple channel plots within the same figure (created outside this function).

    :param channel_events: 1-D NumPy array of event data
    :param label: string to use as the plot title
    :param subplot_ax: Matplotlib Axes instance used to render the plot
    :param xform: an optional Transform instance used to transform the given event data. channel_events can
        be given already pre-processed (compensated and/or transformed), in this case set xform to None.
    :param flagged_events: optional Boolean array of "flagged" events, regions of flagged events will
        be highlighted in red if flagged_events is given.
    :return: None
    """
    if xform:
        channel_events = xform.apply(channel_events)

    bins = int(np.sqrt(channel_events.shape[0]))
    event_range = range(0, channel_events.shape[0])

    subplot_ax.set_title(label, fontsize=16)
    subplot_ax.set_xlabel("Events", fontsize=14)

    subplot_ax.hist2d(
        event_range,
        channel_events,
        bins=[bins, 128],
        cmap='rainbow',
        cmin=1
    )

    if flagged_events is not None:
        starts, ends = _get_false_bounds(flagged_events)

        for i, s in enumerate(starts):
            subplot_ax.axvspan(
                event_range[s],
                event_range[ends[i] - 1],
                facecolor='pink',
                alpha=0.3,
                edgecolor='deeppink'
            )


def _calculate_extent(data_1d, d_min=None, d_max=None, pad=0.0):
    data_min = np.min(data_1d)
    data_max = np.max(data_1d)

    # determine padding to keep min/max events off the edge
    pad_d = max(abs(data_min), abs(data_max)) * pad

    if d_min is None:
        d_min = data_min - pad_d
    if d_max is None:
        d_max = data_max + pad_d

    return d_min, d_max


def render_polygon(vertices):
    """
    Renders a Bokeh polygon for plotting
    :param vertices: list of 2-D coordinates representing vertices of the polygon
    :return: tuple containing the Bokeh ColumnDataSource and polygon glyphs (as Patch object)
    """
    x_coords, y_coords = list(zip(*[v for v in vertices]))

    source = ColumnDataSource(dict(x=x_coords, y=y_coords))

    poly = Patch(
        x='x',
        y='y',
        fill_color=fill_color,
        fill_alpha=gate_fill_alpha,
        line_width=line_width,
        line_color=line_color_contrast
    )

    return source, poly


def render_ranges(dim_minimums, dim_maximums):
    """
    Renders Bokeh Span & BoxAnnotation objects for plotting simple range gates, essentially divider lines.
    There should be no more than 3 items total between dim_minimums & dim_maximums, else the object should
    be rendered as a rectangle.

    :param dim_minimums: list of minimum divider values (max of 2)
    :param dim_maximums: list of maximum divider values (max of 2)
    :return: tuple of Span objects for every item in dim_minimums & dim_maximums
    """
    renderers = []
    left = None
    right = None
    bottom = None
    top = None

    if dim_minimums[0] is not None:
        left = dim_minimums[0]
        renderers.append(
            Span(location=left, dimension='height', line_width=line_width, line_color=line_color)
        )
    if dim_maximums[0] is not None:
        right = dim_maximums[0]
        renderers.append(
            Span(location=right, dimension='height', line_width=line_width, line_color=line_color)
        )
    if len(dim_minimums) > 1:
        if dim_minimums[1] is not None:
            bottom = dim_minimums[1]
            renderers.append(
                Span(location=bottom, dimension='width', line_width=line_width, line_color=line_color)
            )
        if dim_maximums[1] is not None:
            top = dim_maximums[1]
            renderers.append(
                Span(location=top, dimension='width', line_width=line_width, line_color=line_color)
            )

    mid_box = BoxAnnotation(
        left=left,
        right=right,
        bottom=bottom,
        top=top,
        fill_alpha=gate_fill_alpha,
        fill_color=fill_color
    )
    renderers.append(mid_box)

    return renderers


def render_rectangle(dim_minimums, dim_maximums):
    """
    Renders Bokeh Rect object for plotting a rectangle gate.

    :param dim_minimums: list of 2 values representing the lower left corner of a rectangle
    :param dim_maximums: list of 2 values representing the upper right corner of a rectangle
    :return: Bokeh Rect object
    """
    x_center = (dim_minimums[0] + dim_maximums[0]) / 2.0
    y_center = (dim_minimums[1] + dim_maximums[1]) / 2.0
    x_width = dim_maximums[0] - dim_minimums[0]
    y_height = dim_maximums[1] - dim_minimums[1]
    rect = Rect(
        x=x_center,
        y=y_center,
        width=x_width,
        height=y_height,
        fill_color=fill_color,
        fill_alpha=gate_fill_alpha,
        line_width=line_width
    )

    return rect


def render_dividers(x_locs, y_locs):
    """
    Renders lines for divider boundaries (2-D only)
    :param x_locs: list of divider locations in x-axis
    :param y_locs: list of divider locations in y-axis
    :return: list of Bokeh renderer objects
    """
    renderers = []

    for x_loc in x_locs:
        renderers.append(
            Span(location=x_loc, dimension='height', line_width=line_width, line_color=line_color)
        )
    for y_loc in y_locs:
        renderers.append(
            Span(location=y_loc, dimension='width', line_width=line_width, line_color=line_color)
        )

    return renderers


def render_ellipse(center_x, center_y, covariance_matrix, distance_square):
    """
    Renders a Bokeh Ellipse object given the ellipse center point, covariance, and distance square

    :param center_x: x-coordinate of ellipse center
    :param center_y: y-coordinate of ellipse center
    :param covariance_matrix: NumPy array containing the covariance matrix of the ellipse
    :param distance_square: value for distance square of ellipse
    :return: Bokeh Ellipse object
    """
    values, vectors = np.linalg.eigh(covariance_matrix)
    order = values.argsort()[::-1]
    values = values[order]
    vectors = vectors[:, order]

    angle_rads = np.arctan2(*vectors[:, 0][::-1])

    # Width and height are full width (the axes lengths are thus multiplied by 2.0 here)
    width, height = 2.0 * np.sqrt(values * distance_square)

    ellipse = Ellipse(
        x=center_x,
        y=center_y,
        width=width,
        height=height,
        angle=angle_rads,
        line_width=line_width,
        line_color=line_color,
        fill_color=fill_color,
        fill_alpha=gate_fill_alpha
    )

    return ellipse


def plot_histogram(x, x_label='x', bins=None):
    """
    Creates a Bokeh histogram plot of the given 1-D data array.

    :param x: 1-D array of data values
    :param x_label: Label to use for the x-axis
    :param bins: Number of bins to use for the histogram or a string compatible
            with the NumPy histogram function. If None, the number of bins is
            determined by the square root rule.
    :return: Bokeh Figure object containing the histogram
    """
    if bins is None:
        bins = 'sqrt'

    hist, edges = np.histogram(x, density=False, bins=bins)

    tools = "crosshair,hover,pan,zoom_in,zoom_out,box_zoom,undo,redo,reset,save,"

    p = figure(tools=tools)
    p.title.align = 'center'
    p.quad(
        top=hist,
        bottom=0,
        left=edges[:-1],
        right=edges[1:],
        alpha=0.5
    )

    p.y_range.start = 0
    p.xaxis.axis_label = x_label
    p.yaxis.axis_label = 'Event Count'

    return p


def plot_scatter(
        x,
        y,
        x_label=None,
        y_label=None,
        event_mask=None,
        highlight_mask=None,
        x_min=None,
        x_max=None,
        y_min=None,
        y_max=None,
        color_density=True,
        bin_width=4
):
    """
    Creates a Bokeh scatter plot from the two 1-D data arrays.

    :param x: 1-D array of data values for the x-axis
    :param y: 1-D array of data values for the y-axis
    :param x_label: Label for the x-axis
    :param y_label: Labelfor the y-axis
    :param event_mask: Boolean array of events to plot. Takes precedence
            over highlight_mask (i.e. events marked False in event_mask will
            never be plotted).
    :param highlight_mask: Boolean array of event indices to highlight
        in color. Non-highlighted events will be light grey.
    :param x_min: Lower bound of x-axis. If None, channel's min value will
        be used with some padding to keep events off the edge of the plot.
    :param x_max: Upper bound of x-axis. If None, channel's max value will
        be used with some padding to keep events off the edge of the plot.
    :param y_min: Lower bound of y-axis. If None, channel's min value will
        be used with some padding to keep events off the edge of the plot.
    :param y_max: Upper bound of y-axis. If None, channel's max value will
        be used with some padding to keep events off the edge of the plot.
    :param color_density: Whether to color the events by density, similar
        to a heat map. Default is True.
    :param bin_width: Bin size to use for the color density, in units of
        event point size. Larger values produce smoother gradients.
        Default is 4 for a 4x4 grid size.
    :return: A Bokeh Figure object containing the interactive scatter plot.
    """
    # before anything, check for event_mask
    if event_mask is not None:
        # filter x & y
        x = x[event_mask]
        y = y[event_mask]

        # sync highlight_mask if given
        if highlight_mask is not None:
            highlight_mask = highlight_mask[event_mask]

    if len(x) > 0:
        x_min, x_max = _calculate_extent(x, d_min=x_min, d_max=x_max, pad=0.02)
    if len(y) > 0:
        y_min, y_max = _calculate_extent(y, d_min=y_min, d_max=y_max, pad=0.02)

    if y_max > x_max:
        radius_dimension = 'y'
        radius = 0.003 * y_max
    else:
        radius_dimension = 'x'
        radius = 0.003 * x_max

    if color_density:
        # bin size set to cover NxN radius (radius size is percent of view)
        # can be set by user via bin_width kwarg
        bin_count = int(1 / (bin_width * 0.003))

        # But that's just the bins needed for the requested plot ranges.
        # We need to extend those bins to the full data range
        x_view_range = x_max - x_min
        y_view_range = y_max - y_min

        x_data_min = np.min(x)
        x_data_max = np.max(x)
        y_data_min = np.min(y)
        y_data_max = np.max(y)
        x_data_range = x_data_max - x_data_min
        y_data_range = y_data_max - y_data_min

        x_bin_multiplier = x_data_range / x_view_range
        x_bin_count = int(x_bin_multiplier * bin_count)
        y_bin_multiplier = y_data_range / y_view_range
        y_bin_count = int(y_bin_multiplier * bin_count)

        # avoid bin count of zero
        if x_bin_count <= 0:
            x_bin_count = 1
        if y_bin_count <= 0:
            y_bin_count = 1

        cd_x_min = x_data_min - (x_data_range / x_bin_count)
        cd_x_max = x_data_max + (x_data_range / x_bin_count)
        cd_y_min = y_data_min - (y_data_range / y_bin_count)
        cd_y_max = y_data_max + (y_data_range / y_bin_count)

        hist_data, x_edges, y_edges = np.histogram2d(
            x,
            y,
            bins=[x_bin_count, y_bin_count],
            range=[[cd_x_min, cd_x_max], [cd_y_min, cd_y_max]]
        )
        z = interpn(
            (0.5 * (x_edges[1:] + x_edges[:-1]), 0.5 * (y_edges[1:] + y_edges[:-1])),
            hist_data,
            np.vstack([x, y]).T,
            method="linear",  # use linear not spline, spline tends to overshoot into negative values
            bounds_error=False
        )
        z[np.isnan(z)] = 0

        # sort by density (z) so the more dense points are on top for better
        # color display
        idx = z.argsort()
        x, y, z = x[idx], y[idx], z[idx]
        if highlight_mask is not None:
            # re-order the highlight indices to match
            highlight_mask = highlight_mask[idx]
    else:
        z = np.zeros(len(x))

    colors_array = new_jet(colors.Normalize()(z))
    z_colors = np.array([
        "#%02x%02x%02x" % (int(c[0] * 255), int(c[1] * 255), int(c[2] * 255)) for c in colors_array
    ])

    if highlight_mask is not None:
        z_colors[~highlight_mask] = "#d3d3d3"
        fill_alpha = np.zeros(len(z_colors))
        fill_alpha[~highlight_mask] = 0.3
        fill_alpha[highlight_mask] = 0.4

        highlight_idx = np.flatnonzero(highlight_mask)
        non_light_idx = np.flatnonzero(~highlight_mask)
        final_idx = np.concatenate([non_light_idx, highlight_idx])

        x = x[final_idx]
        y = y[final_idx]
        z_colors = z_colors[final_idx]
        fill_alpha = fill_alpha[final_idx]
    else:
        fill_alpha = 0.4

    tools = "crosshair,hover,pan,zoom_in,zoom_out,box_zoom,undo,redo,reset,save,"
    p = figure(
        tools=tools,
        x_range=(x_min, x_max),
        y_range=(y_min, y_max)
    )

    p.xaxis.axis_label = x_label
    p.yaxis.axis_label = y_label

    p.scatter(
        x,
        y,
        radius=radius,
        radius_dimension=radius_dimension,
        fill_color=z_colors,
        fill_alpha=fill_alpha,
        line_color=None
    )

    return p

def plot_gate(
        gate_id,
        gating_strategy: GatingStrategy,
        sample,
        subsample_count=10000,
        random_seed=1,
        event_mask=None,
        x_min=None,
        x_max=None,
        y_min=None,
        y_max=None,
        color_density=True,
        bin_width=4
):
    """
    Returns an interactive plot for the specified gate. The type of plot is
    determined by the number of dimensions used to define the gate: single
    dimension gates will be histograms, 2-D gates will be returned as a
    scatter plot.

    :param gate_id: tuple of gate name and gate path (also a tuple)
    :param gating_strategy: GatingStrategy containing gate_id
    :param sample: Sample instance to plot
    :param subsample_count: Number of events to use as a sub-sample. If the number of
        events in the Sample is less than the requested sub-sample count, then the
        maximum number of available events is used for the sub-sample.
    :param random_seed: Random seed used for sub-sampling events
    :param event_mask: Boolean array of events to plot (i.e. parent gate event membership)
    :param x_min: Lower bound of x-axis. If None, channel's min value will
        be used with some padding to keep events off the edge of the plot.
    :param x_max: Upper bound of x-axis. If None, channel's max value will
        be used with some padding to keep events off the edge of the plot.
    :param y_min: Lower bound of y-axis. If None, channel's min value will
        be used with some padding to keep events off the edge of the plot.
    :param y_max: Upper bound of y-axis. If None, channel's max value will
        be used with some padding to keep events off the edge of the plot.
    :param color_density: Whether to color the events by density, similar
        to a heat map. Default is True.
    :param bin_width: Bin size to use for the color density, in units of
        event point size. Larger values produce smoother gradients.
        Default is 4 for a 4x4 grid size.
    :return: A Bokeh Figure object containing the interactive scatter plot.
    """
    (gate_name, gate_path) = gate_id
    sample_id = sample.id
    gate = gating_strategy.get_gate(gate_name, gate_path=gate_path, sample_id=sample_id)

    # check for a boolean gate, there's no reasonable way to plot these
    if isinstance(gate, gates.BooleanGate):
        raise TypeError("Plotting Boolean gates is not allowed (gate %s)" % gate.gate_name)

    dim_ids_ordered = []
    dim_is_ratio = []
    dim_comp_refs = []
    dim_min = []
    dim_max = []
    for i, dim in enumerate(gate.dimensions):
        if isinstance(dim, dimension.RatioDimension):
            dim_ids_ordered.append(dim.ratio_ref)
            tmp_dim_min = dim.min
            tmp_dim_max = dim.max
            is_ratio = True
        elif isinstance(dim, dimension.QuadrantDivider):
            dim_ids_ordered.append(dim.dimension_ref)
            tmp_dim_min = None
            tmp_dim_max = None
            is_ratio = False
        else:
            dim_ids_ordered.append(dim.id)
            tmp_dim_min = dim.min
            tmp_dim_max = dim.max
            is_ratio = False

        dim_min.append(tmp_dim_min)
        dim_max.append(tmp_dim_max)
        dim_is_ratio.append(is_ratio)
        dim_comp_refs.append(dim.compensation_ref)

    # dim count determines if we need a histogram, scatter, or multi-scatter
    dim_count = len(dim_ids_ordered)
    if dim_count == 1:
        gate_type = 'hist'
    elif dim_count == 2:
        gate_type = 'scatter'
    elif dim_count > 2:
        raise NotImplementedError("Plotting of gates with >2 dimensions is not supported")
    else:
        # there are no dimensions
        raise ValueError("Gate %s appears to not reference any dimensions" % gate_name)

    # Apply requested subsampling
    sample.subsample_events(subsample_count=subsample_count, random_seed=random_seed)
    # noinspection PyProtectedMember
    events = gating_strategy._preprocess_sample_events(
        sample,
        gate
    )

    # Use event mask, if given
    if event_mask is not None:
        is_subsample = np.zeros(sample.event_count, dtype=bool)
        is_subsample[sample.subsample_indices] = True
        idx_to_plot = np.logical_and(event_mask, is_subsample)
    else:
        idx_to_plot = sample.subsample_indices

    x = events.loc[idx_to_plot, dim_ids_ordered[0]].values

    dim_ids = []

    if dim_is_ratio[0]:
        dim_ids.append(dim_ids_ordered[0])
        x_pnn_label = None
    else:
        try:
            x_index = sample.get_channel_index(dim_ids_ordered[0])
        except ValueError:
            # might be a label reference in the comp matrix
            matrix = gating_strategy.get_comp_matrix(dim_comp_refs[0])
            try:
                matrix_dim_idx = matrix.fluorochomes.index(dim_ids_ordered[0])
            except ValueError:
                raise ValueError("%s not found in list of matrix fluorochromes" % dim_ids_ordered[0])
            detector = matrix.detectors[matrix_dim_idx]
            x_index = sample.get_channel_index(detector)

        x_pnn_label = sample.pnn_labels[x_index]

        if sample.pns_labels[x_index] != '':
            dim_ids.append('%s (%s)' % (sample.pns_labels[x_index], x_pnn_label))
        else:
            dim_ids.append(sample.pnn_labels[x_index])

    y_pnn_label = None

    if dim_count > 1:
        if dim_is_ratio[1]:
            dim_ids.append(dim_ids_ordered[1])

        else:
            try:
                y_index = sample.get_channel_index(dim_ids_ordered[1])
            except ValueError:
                # might be a label reference in the comp matrix
                matrix = gating_strategy.get_comp_matrix(dim_comp_refs[1])
                try:
                    matrix_dim_idx = matrix.fluorochomes.index(dim_ids_ordered[1])
                except ValueError:
                    raise ValueError("%s not found in list of matrix fluorochromes" % dim_ids_ordered[1])
                detector = matrix.detectors[matrix_dim_idx]
                y_index = sample.get_channel_index(detector)

            y_pnn_label = sample.pnn_labels[y_index]

            if sample.pns_labels[y_index] != '':
                dim_ids.append('%s (%s)' % (sample.pns_labels[y_index], y_pnn_label))
            else:
                dim_ids.append(sample.pnn_labels[y_index])

    if gate_type == 'scatter':
        y = events.loc[idx_to_plot, dim_ids_ordered[1]].values

        p = plot_scatter(
            x,
            y,
            x_label=dim_ids[0],
            y_label=dim_ids[1],
            x_min=x_min,
            x_max=x_max,
            y_min=y_min,
            y_max=y_max,
            color_density=color_density,
            bin_width=bin_width
        )
    elif gate_type == 'hist':
        p = plot_histogram(x, dim_ids[0])
    else:
        raise NotImplementedError("Only histograms and scatter plots are supported in this version of FlowKit")

    if isinstance(gate, gates.PolygonGate):
        source, glyph = render_polygon(gate.vertices)
        p.add_glyph(source, glyph)
    elif isinstance(gate, gates.EllipsoidGate):
        ellipse = render_ellipse(
            gate.coordinates[0],
            gate.coordinates[1],
            gate.covariance_matrix,
            gate.distance_square
        )
        p.add_glyph(ellipse)
    elif isinstance(gate, gates.RectangleGate):
        # rectangle gates in GatingML may not actually be rectangles, as the min/max for the dimensions
        # are options. So, if any of the dim min/max values are missing it is essentially a set of ranges.

        if None in dim_min or None in dim_max or dim_count == 1:
            renderers = render_ranges(dim_min, dim_max)

            p.renderers.extend(renderers)
        else:
            # a true rectangle
            rect = render_rectangle(dim_min, dim_max)
            p.add_glyph(rect)
    elif isinstance(gate, gates.QuadrantGate):
        x_locations = []
        y_locations = []

        for div in gate.dimensions:
            if div.dimension_ref == x_pnn_label:
                x_locations.extend(div.values)
            elif div.dimension_ref == y_pnn_label and y_pnn_label is not None:
                y_locations.extend(div.values)

        renderers = render_dividers(x_locations, y_locations)
        p.renderers.extend(renderers)
    else:
        raise NotImplementedError(
            "Plotting of %s gates is not supported in this version of FlowKit" % gate.__class__
        )

    if gate_path is not None:
        full_gate_path = gate_path[1:]  # omit 'root'
        full_gate_path = full_gate_path + (gate_name,)
        sub_title = ' > '.join(full_gate_path)

        # truncate beginning of long gate paths
        if len(sub_title) > 72:
            sub_title = '...' + sub_title[-69:]
        p.add_layout(
            Title(text=sub_title, text_font_style="italic", text_font_size="1em", align='center'),
            'above'
        )
    else:
        p.add_layout(
            Title(text=gate_name, text_font_style="italic", text_font_size="1em", align='center'),
            'above'
        )

    plot_title = "%s" % sample_id
    p.add_layout(
        Title(text=plot_title, text_font_size="1.1em", align='center'),
        'above'
    )

    return p