from settings import CSS_URL, IMG_URL


def urls(request):
    return {'CSS_URL': CSS_URL, 'IMG_URL': IMG_URL}
