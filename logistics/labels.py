#!/bin/env python
# coding=utf-8

from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


pdfmetrics.registerFont(TTFont('Ldcode', 'static/fonts/ldcode.ttf'))
pdfmetrics.registerFont(TTFont('Roboto', 'static/fonts/Roboto-Regular.ttf'))
pdfmetrics.registerFont(TTFont('Roboto-Bold', 'static/fonts/Roboto-Bold.ttf'))
pdfmetrics.registerFont(TTFont('3of9', 'static/fonts/FREE3OF9.TTF'))


class PrintableArea(object):
    """
    Clase de impresion de lineas con capacidad de estirar (o encoger) el lienzo
    automaticamente, tratando siempre de:
        1) Utilizar el maximo posible del area propuesta
        2) Que nada del texto salga del area propuesta
    """

    def __init__(
            self, canvas, xpos, ypos, width, height, default_font='Roboto',
            default_size=8):
        self.current_position = (0, height)
        self.max_line_width = 1
        self.max_paragraph_height = 1
        self.lines = []
        self.canvas = canvas

        self.default_font = default_font
        self.default_font_size = default_size  # renombrar

        self.translation = xpos, ypos
        self.width = width
        self.height = height

    def getFont(self, font=None, bold=False):
        if not font:
            font = self.default_font

        if bold:
            font = font + '-Bold'

        return font

    def lineHeight(self, family, size):
        return int(size * 1)

    def debug_pattern(self):
        radius = 3 * mm
        self.canvas.circle(0, 0, radius)
        self.canvas.line(0, 0, self.width, -self.height)
        self.canvas.circle(self.width, -self.height, radius)

    def putLine(self, line, bold=False, br=True, font='Roboto'):
        # TODO: la implementacion del <br> no funciona
        self.max_line_width = max(self.max_line_width, self.canvas.stringWidth(line, self.getFont(bold=bold, font=font), self.default_font_size))
        self.lines.append((line, bold, font))
        if br:
            self.max_paragraph_height += self.lineHeight(font, self.default_font_size)

    def draw(self, debug=False, stretch=True):
        self.canvas.saveState()
        self.canvas.translate(*self.translation)

        if debug:
            self.debug_pattern()

        self.tt = self.canvas.beginText()
        self.tt.setTextOrigin(0, 0 - self.default_font_size)

        sfactor = 1
        if stretch:
            horizontal_sfactor = self.width / float(self.max_line_width)
            vertical_sfactor = self.height / float(self.max_paragraph_height)
            sfactor = min(horizontal_sfactor, vertical_sfactor)
            sfactor = self.canvas.scale(sfactor, sfactor)

        for line, bold, font in self.lines:
            self.tt.setFont(self.getFont(font, bold), self.default_font_size)
            self.tt.setLeading(self.default_font_size)
            self.tt.textLine(line)

        self.canvas.drawText(self.tt)
        self.canvas.restoreState()


class Label(object):

    def __init__(self, canvas, width, height, topm, rightm, bottomm, leftm):
        self.width = width - leftm - rightm
        self.height = height - topm - bottomm
        self.canvas = canvas

        # self.canvas.rect(0, 0, width, height) # Comentar/Descomentar para debugear

        self.canvas.saveState()
        self.canvas.translate(leftm, bottomm)

    def draw(self):
        # do something
        self.label_done()

    def label_done(self):
        self.canvas.restoreState()


class SheetLayout(object):
    width = 100 * mm
    height = 200 * mm

    spots = ((0, (0,)),)

    def __init__(self, label_type, canvas, debug=None):
        self.canvas = canvas
        self.label_type = label_type
        self.debug = debug

    def iterator(self):
        while True:
            for y, x_list in self.spots:
                for x in x_list:
                    # print x, y
                    self.canvas.saveState()
                    self.canvas.translate(x, y)
                    if self.debug:
                        self.canvas.circle(0, 0, 2 * mm)
                    yield self.label_type(self.canvas)
                    self.canvas.restoreState()
            self.canvas.showPage()

    def flush(self):
        self.canvas.restoreState()
        self.canvas.showPage()


class LogisticsLabel(Label):
    """
    This is a label object. Attributes support multiple lines, you have to separate them with \n
    """
    width = 59 * mm
    height = 30 * mm
    # Margins
    topm = 0 * mm
    rightm = 2 * mm
    bottomm = 2 * mm
    leftm = 2 * mm

    def __init__(self, canvas):

        self.name = ''
        self.address = ''
        self.route = ''
        self.route_suffix = ''
        self.route_order = None
        self.envelope = False
        self.new = False
        self.has_invoice = False
        self.message_for_contact = ''
        self.message_for_distributor = ''
        self.special_instructions = False
        self.extra_field = False

        self.octavio = (self.height - self.topm - self.bottomm) / 8

        super(LogisticsLabel, self).__init__(canvas, self.width, self.height, self.topm, self.rightm,
                                             self.bottomm, self.leftm)

    def draw(self, debug=False, barcode_h=0):
        """ Genero 5 areas con diferentes tama~os (medidos en octavios = octavos del alto total del canvas) """

        # Area de codigo de barras
        p0 = PrintableArea(self.canvas, 0, self.height, self.width, barcode_h)
        if barcode_h:
            self.octavio = (self.height - barcode_h - self.topm - self.bottomm) / 8
            p0.putLine(self.barcode, font='3of9')

        # Area de Nombre
        p1 = PrintableArea(self.canvas, 0, self.height - barcode_h, self.width, 1 * self.octavio)
        for line in self.name.splitlines():
            p1.putLine(line)

        # Area de Direccion
        p2 = PrintableArea(self.canvas, 0, self.height - barcode_h - 1 * self.octavio, self.width, 4 * self.octavio)
        for line in self.address.splitlines():
            p2.putLine(line, bold=True)

        # Area de comunicacion cliente o distribuidor
        p3 = PrintableArea(self.canvas, 0, self.height - barcode_h - 5 * self.octavio, self.width, 2 * self.octavio)

        if not self.message_for_contact:  # No hay comunicacion cliente, podemos usar este espacio para mensaje distribuidor
            for line in self.message_for_distributor.splitlines():
                p3.putLine(line, bold=True)

        else:  # Hay comunicacion cliente, se pone mensaje distribuidor en area de direccion
            for line in self.message_for_distributor.splitlines():
                p2.putLine(line, bold=True)

            for line in self.message_for_contact.splitlines():
                p3.putLine(line)

        # Area de ruta
        p4 = PrintableArea(self.canvas, 0, self.height - barcode_h - 7 * self.octavio, self.width, 1 * self.octavio)
        p4.putLine(">R_%s : O_%s %s" % (self.route, self.route_order or '?', self.route_suffix), bold=True)

        # Area de iconos
        p5 = PrintableArea(self.canvas, self.width - 10 * mm, 1.7 * self.octavio, 10 * mm, 1.3 * self.octavio)
        icons = ''
        if self.new:
            icons += 'E'
        if self.envelope:
            icons += 'D'
        if self.has_invoice:
            icons += 'C'
        if self.special_instructions:
            icons += 'G'
        if self.extra_field:
            icons += 'F'
        p5.putLine(icons, font='Ldcode')

        p0.draw(debug=debug, stretch=True)
        p1.draw(debug=debug, stretch=True)
        p2.draw(debug=debug, stretch=True)
        p3.draw(debug=debug, stretch=True)
        p4.draw(debug=debug, stretch=True)
        p5.draw(debug=debug, stretch=True)

        self.label_done()

    def separador(self):
        p1 = PrintableArea(self.canvas, 0, self.height - 3 * self.octavio, self.width, 4 * self.octavio)
        p1.putLine("++++++++++++")
        p1.draw()
        self.label_done()


class LogisticsLabelA4(LogisticsLabel):
    width = 63.5 * mm
    height = 20.4 * mm
    rightm = 2 * mm
    leftm = 2 * mm
    bottomm = 0 * mm
    topm = 0 * mm


class LogisticsLabel96x30(LogisticsLabel):
    width = 90.0 * mm
    height = 25.0 * mm


class LogisticsLabelTroquelada(LogisticsLabel):
    width = 55 * mm
    height = 44 * mm
    barrah = 15 * mm

    def draw(self, cod_barra):
        self.cod_barra = cod_barra
        super(LogisticsLabelTroquelada, self).draw(False, self.barrah)


class SheetA4(SheetLayout):
    # rotola A43/18
    width = 210 * mm
    height = 297 * mm

    spots = (
        # y, (x1, x2, x3) from bottom-left, generated with:
        # print(',\n'.join('(%.1f * mm, (8 * mm, 74 * mm, 140 * mm))' % (
        #     12 + 46.5 * i) for i in range(6)))
        (12.0 * mm, (8 * mm, 74 * mm, 140 * mm)),
        (58.5 * mm, (8 * mm, 74 * mm, 140 * mm)),
        (105.0 * mm, (8 * mm, 74 * mm, 140 * mm)),
        (151.5 * mm, (8 * mm, 74 * mm, 140 * mm)),
        (198.0 * mm, (8 * mm, 74 * mm, 140 * mm)),
        (244.5 * mm, (8 * mm, 74 * mm, 140 * mm))
    )


class Roll(SheetLayout):
    width = 63 * mm
    height = 33 * mm


class RollTroquelado(SheetLayout):
    width = 55 * mm
    height = 44 * mm


class Roll96x30(SheetLayout):
    width = 96 * mm
    height = 30 * mm


class LdcodeTest(LogisticsLabel):

    def __init__(self, canvas):
        super(LdcodeTest, self).__init__(canvas)

    def draw(self, debug=False):

        p1 = PrintableArea(self.canvas, 0, self.height, self.width, self.height)
        p1.putLine('abcdefghijk', font='Ldcode')
        p1.putLine('lmnopqrstuvz', font='Ldcode')
        p1.putLine('ABCDEFGHIJK', font='Ldcode')
        p1.putLine('LMNOPQRSTUVZ', font='Ldcode')
        p1.putLine('.:,;(*!?\')', font='Ldcode')
        p1.putLine('123456789', font='Ldcode')
        p1.draw(debug=debug, stretch=True)
        self.canvas.showPage()


def main():

    path_b = './test_label.pdf'

    fd = open(path_b, 'w')

    # A4
    canvas = Canvas(fd, pagesize=(SheetA4.width, SheetA4.height))
    hoja = SheetA4(LogisticsLabelA4, canvas)

    # Rollo
    # canvas = Canvas(fd, pagesize=(Rollo.width, Rollo.height))
    # hoja = Rollo(EtiquetaDistribucion, canvas)

    iterator = hoja.iterator()

    for n in range(33):
        e = iterator.next()
        e.name = 'Ernesto Pizantolli'.upper()
        e.address = 'Florida 1453\nEsquina Soriano'
        e.envelope = True
        e.new = True
        e.has_invoice = True
        e.route = 18
        e.route_order = 5
        e.route_suffix = 'LUN'
        e.message_for_distributor = '>Cuidado con el perro'
        e.message_for_contact = 'Te llega por cortesia del\ns Big Love Daddy dsfsd s  frsdfd sdf'
        e.draw(debug=False)

    hoja.flush()
    canvas.save()


if __name__ == '__main__':
    main()
