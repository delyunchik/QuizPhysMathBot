import pylab

# formula = r'$x=3^2, y = \frac{1}{\frac{2}{3}}$'
formula = r'$1 - \cos^2\alpha$'

fig = pylab.figure()
text = fig.text(0, 0, formula)

# Saving the figure will render the text.
dpi = 300
fig.savefig('formula.png', dpi=dpi)

# Now we can work with text's bounding box.
bbox = text.get_window_extent()
width, height = bbox.size / float(dpi) + 0.005
# Adjust the figure size so it can hold the entire text.
fig.set_size_inches((width, height))

# Adjust text's vertical position.
dy = (bbox.ymin/float(dpi))/height
text.set_position((0, -dy))

# Save the adjusted text.
fig.savefig('formula.png', dpi=dpi)
