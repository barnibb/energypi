import json
import unittest
from pathlib import Path


class ProjectInfoTests(unittest.TestCase):
    def test_code_line_comparison_is_documented(self):
        info=json.loads(Path('project_info.json').read_text())
        section=next(section for section in info['sections'] if section['title']=='Projektstruktur: Dateien und Ordner')
        self.assertEqual(section['table']['headers'],['Version','Produktive Dateien','Codezeilen','Hinweis'])
        self.assertEqual(section['table']['rows'][0][:3],['1.49.2','125','6.142'])
        self.assertEqual(section['table']['rows'][1][:3],['1.49.1','125','6.142'])
        self.assertIn('ohne Tests',section['paragraphs'][-1])


if __name__=='__main__':
    unittest.main()
