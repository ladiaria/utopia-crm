import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase

from core.utils import read_uploaded_csv, read_uploaded_csv_rows, uploaded_csv_content


def uploaded(content):
    return SimpleUploadedFile("planilla.csv", content)


class UploadedCsvContentTestCase(SimpleTestCase):
    def text(self, raw):
        return uploaded_csv_content(uploaded(raw))[0].read()

    def test_encodings(self):
        cases = {
            "utf-8": "José".encode("utf-8"),
            "utf-8 with BOM": "José".encode("utf-8-sig"),
            "plain Excel CSV": "José".encode("cp1252"),
        }
        for name, raw in cases.items():
            with self.subTest(name):
                self.assertEqual(self.text(raw), "José")

    def test_cp1252_symbols_are_read_right(self):
        # In latin-1 these are control characters
        self.assertEqual(self.text("O’Neil – 5 €".encode("cp1252")), "O’Neil – 5 €")

    def test_bytes_that_cp1252_lacks_fall_back_to_latin1(self):
        self.assertEqual(self.text(b"Jos\xe9 \x81"), "José \x81")

    def test_delimiter(self):
        cases = {
            "comma": ("email,nombre\na@b.com,Ana\nc@d.com,Beto\n", ","),
            "semicolon": ("email;nombre\na@b.com;Ana\nc@d.com;Beto\n", ";"),
            "one column": ("contact_id\n123\n456\n", ","),
            "semicolon, commas inside the values": (
                "email;direccion;ciudad\na@b.com;Calle 1, apto 2;Montevideo\nc@d.com;Calle 3, apto 4;Salto\n",
                ";",
            ),
            "comma, quoted commas": (
                'email,direccion,ciudad\na@b.com,"Calle 1, apto 2",Montevideo\nc@d.com,"Calle 3, apto 4",Salto\n',
                ",",
            ),
            "comma, a semicolon inside a value": (
                'email,direccion,ciudad\na@b.com,"Calle 1; apto 2",Montevideo\nc@d.com,Calle 3,Salto\n',
                ",",
            ),
            "empty": ("", ","),
        }
        for name, (content, delimiter) in cases.items():
            with self.subTest(name):
                self.assertEqual(uploaded_csv_content(uploaded(content.encode()))[1], delimiter)


class ReadUploadedCsvTestCase(SimpleTestCase):
    def rows(self, content):
        reader, _delimiter = read_uploaded_csv(uploaded(content.encode()))
        return list(reader)

    def test_short_row_gets_empty_strings(self):
        self.assertEqual(self.rows("a,b\n1\n"), [{"a": "1", "b": ""}])

    def test_long_row_keeps_its_columns_and_only_string_keys(self):
        self.assertEqual(self.rows("a,b\n1,2,3\n"), [{"a": "1", "b": "2", "extra_columns": ["3"]}])

    def test_spaces_around_column_names(self):
        self.assertEqual(self.rows(" a , b\n1,2\n"), [{"a": "1", "b": "2"}])

    def test_empty_file(self):
        reader, _delimiter = read_uploaded_csv(uploaded(b""))

        self.assertEqual(reader.fieldnames, [])
        self.assertEqual(list(reader), [])

    def test_quoted_line_break(self):
        self.assertEqual(self.rows('a,b\n"1\n2",3\n'), [{"a": "1\n2", "b": "3"}])

    def test_any_file_object(self):
        reader, _delimiter = read_uploaded_csv(io.BytesIO(b"a\n1\n"))

        self.assertEqual(list(reader), [{"a": "1"}])


class ReadUploadedCsvRowsTestCase(SimpleTestCase):
    def test_bom_does_not_stick_to_the_first_value(self):
        self.assertEqual(list(read_uploaded_csv_rows(uploaded("1;a\n".encode("utf-8-sig")))), [["1", "a"]])
