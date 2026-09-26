from rest_framework.pagination import PageNumberPagination

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100
    page_query_param = 'page'

    def paginate_queryset(self, queryset, request, view=None):
        paginate_param = request.query_params.get('paginate', '').lower()
        has_page = 'page' in request.query_params
        
        if paginate_param == 'true' or has_page:
            return super().paginate_queryset(queryset, request, view=view)
        
        return None
