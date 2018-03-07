# -*- coding: utf-8 -*-
"""
Create html5 report from session
WIP

@author: Jussi (jnu@iki.fi)
"""

import mpld3

import gaitutils
from gaitutils import report

pl = gaitutils.Plotter()
pl.open_nexus_trial()
pl.layout = [['HipAnglesX', 'KneeAnglesX']]

pl.plot_trial(show=False)
fig_js = mpld3.fig_to_html(pl.fig)

# html snippet for video
vid = """
<video src="%s" controls>
</video>
""" % '/Users/hus20664877/Desktop/Vicon/vicon_data/test/Verrokki6v_IN/2015_10_22_girl6v_IN/2015_10_22_girl6v_IN57.64826554.20151022144140.ogv'

context = {'video': vid, 'fig': fig_js}
html_ = report.render_template('default.html', context)

with open('foox.html', 'w') as f:
    f.write(html_)
