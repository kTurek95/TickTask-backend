from rest_framework.pagination import PageNumberPagination

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10  # domyślnie 10 na stronę
    page_size_query_param = "page_size" # pozwala zmienić przez ?page_size=
    max_page_size = 100 # górny limit bezpieczeństwa