import model

def test_ocr_parse():
    model.ocr_parse("test.pdf")

def test_content_structure():
    ret = model.content_structure("test.txt")
    print(ret)

def test_parse_pdf():
    ret = model.parse_pdf("test.pdf")
    print(ret)
if __name__ == '__main__':
    test_parse_pdf()