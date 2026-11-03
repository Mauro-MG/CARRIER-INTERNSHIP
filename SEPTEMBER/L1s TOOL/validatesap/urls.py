from django.urls import path

from .views import historical_validation_detail, index, save_results, validation_history

app_name = "validatesap"
urlpatterns = [
    path("", index, name="index"),
    path("save/", save_results, name="save_results"),
    path("history/", validation_history, name="history"),
    path("history/<str:tumbling_name>/", historical_validation_detail, name="history_detail"),
]
