from qgis.core import *
import qgis.utils
import processing
from qgis.gui import QgsMessageBar
from PyQt4.QtCore import *
from PyQt4.QtGui import *


class Linepart:
	_id = None
	_points = []
	_before = None
	_after = None
	_status = 0 # 0 = include and possibly connect, 1 = include as-is, never connect, 2 = dont include


	def __init__(self, original_index, points):
		assert(len(points) > 1)

		self._id = original_index
		self._points = points
		if self._points[0] == self._points[-1]:
			# one-part loop detected. this _can_ be ambiguous - a loop can never be connected to another line since
			# which end should be connected?
			self._status = 1


	def maybe_connect_with(self, other):
		assert(other is not self)

		if self._status == 2 or other._status == 2:
			return

		p=self._points
		op=other.points_start_to_end()

		if p[-1] == op[0]:
			if self._after or other._before:
				# this is ambiguous
				self._status = 2
				other._status = 2
				return
			if self._status == 1 or other._status == 1:
				self._status = 2
				other._status = 2
				return
			self._after = other
			other._before = self

		if p[0] == op[-1]:
			if self._before or other._after:
				# this is ambiguous
				self._status = 2
				other._status = 2
				return
			if self._status == 1 or other._status == 1:
				self._status = 2
				other._status = 2
				return
			self._before = other
			other._after = self

		if p[-1] == op[-1]:
			if self._after or other._after:
				# this is ambiguous
				self._status = 2
				other._status = 2
				return
			if self._status == 1 or other._status == 1:
				self._status = 2
				other._status = 2
				return
			self._after = other
			other._after = self

		if p[0] == op[0]:
			if self._before or other._before:
				# this is ambiguous
				self._status = 2
				other._status = 2
				return
			if self._status == 1 or other._status == 1:
				self._status = 2
				other._status = 2
				return
			self._before = other
			other._before = self


	def traverse_from(self, frm):
		if self._before == frm:
			p=self.points_start_to_end()
			return (self.shared_point_at_start(), p, self.shared_point_at_end(), self._after)
		elif self._after == frm:
			p=self.points_start_to_end()
			p.reverse()
			return (self.shared_point_at_end(), p, self.shared_point_at_start(), self._before)
		else:
			return ([], None)


	def points_start_to_end(self):
		px1 = 0
		if self._before: px1 += 1
		px2 = len(self._points)
		if self._after: px2 -= 1
		return self._points[px1:px2]


	def shared_point_at_start(self):
		if self._before:
			return self._points[0]
		else:
			return None


	def shared_point_at_end(self):
		if self._after:
			return self._points[-1]
		else:
			return None


	def at_start(self):
		return self._before


	def at_end(self):
		return self._after


	def disabled(self):
		return self._status == 2
		

	def prnt(self):
		print "linepart",self,"------------------"
		print "   id:          ",self._id
		print "   status:      ",self._status
		print "   before:      ",self._before
		print "   after:       ",self._after
		print "   n points:    ",len(self._points)
		print "   first point: ",self._points[0]
		print "   last point:  ",self._points[0]
		print "----------------------------------"
		

class MultilinejoinBatch:
	def __init__(self, iface):
		self.iface=iface


	def initGui(self):
		self.action = QAction("Multiline Join", self.iface.mainWindow())
		self.action.setObjectName("multiline-join")
		QObject.connect(self.action, SIGNAL("triggered()"), self.run)
		self.iface.addPluginToVectorMenu("&Multiline Join", self.action)


	def unload(self):
		self.iface.removePluginVectorMenu("&Multiline Join", self.action)


	def run(self):
		layer=self.iface.activeLayer()
		if layer and layer.dataProvider().capabilities() & QgsVectorDataProvider.ChangeGeometries:
			parts_before_total = 0
			parts_after_total = 0
			parts_included_total = 0
			done_anything=False
			for feature in processing.features(layer):
				geom = feature.geometry()
				if geom.type() == QGis.Line and geom.isMultipart():
					parts = geom.asMultiPolyline()

					lineparts = []
					for px in range(0, len(parts)):
						if len(parts[px]) > 1:
							lp = Linepart(px, parts[px])
							lineparts.append(lp)
					for px in range(0, len(lineparts)):
						for px2 in range(px + 1, len(lineparts)):
							lineparts[px].maybe_connect_with(lineparts[px2])

					seen = {}
					included = {}
					new_parts = []

					for pa in lineparts:
						if pa in seen:
							continue

						if pa.disabled():
							continue

						seen[pa]=True

						points = []
						abort_part=False
						pa_last=pa
						pa_curr=pa.at_start()
						while pa_curr:
							if pa_curr == pa:
								# multi-part loop detected. multi-part loops are ambiguous since
								# where should the start/endpoint be?
								# 
								# all parts in the loop are now marked
								# as seen since we are back were we
								# started and we will just abort.
								abort_part=True
								break
							seen[pa_curr]=True
							shpt1, p, shpt2, pa_next =pa_curr.traverse_from(pa_last)
							p.reverse()
							points[0:0] = p + [shpt1]
							included[pa_curr]=True
							pa_last=pa_curr
							pa_curr=pa_next
						if abort_part:
							continue
						points.extend(pa.points_start_to_end())
						included[pa]=True
						pa_last=pa
						pa_curr=pa.at_end()
						while pa_curr:
							seen[pa_curr]=True
							shpt1, p, shpt2, pa_next=pa_curr.traverse_from(pa_last)
							points.extend([shpt1] + p)
							included[pa_curr]=True
							pa_last=pa_curr
							pa_curr=pa_next

						new_parts.append(points)
								
#					print "feature", feature, "(",feature.id(),")-----"
#					print "parts before:", len(parts)
#					print "parts after:", len(new_parts)
#					np=0
#					for p in parts:
#						np+=len(p)
#					print "number of points before:", np
#					np=0
#					for p in new_parts:
#						np+=len(p)
#					print "number of points after:", np
#					print "-----"

					if len(parts) != len(new_parts):
						if not done_anything:
							done_anything=True
							layer.beginEditCommand("Multiline Join")

						g = QgsGeometry.fromMultiPolyline(new_parts)
						layer.changeGeometry(feature.id(), g)
			#			layer.addFeatures([f])

						parts_before_total += len(parts)
						parts_after_total += len(new_parts)
						parts_included_total += len(included)

			if done_anything:
#				print "actually did modify something"
				layer.endEditCommand()
				layer.triggerRepaint()

				self.iface.messageBar().pushMessage("Multiline Join",
					str(parts_included_total) + "/" + str(parts_before_total) + \
					" parts -> " + str(parts_after_total) + " parts", level=QgsMessageBar.INFO)
