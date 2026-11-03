from django.shortcuts import render
from django.views.decorators.http import require_POST

from .forms import ValidationForm
from .services.csv_service import (
    CsvServiceError,
    InvalidSavedValidationError,
    ResultsFileExistsError,
    SavedValidationNotFoundError,
    filter_saved_validations,
    list_saved_validations,
    load_results_csv,
    result_filename,
    save_results_csv,
)
from .services.processing import process
from .services.snapshots import load_comparison_snapshot, store_comparison_snapshot


def index(request):
    result = None
    save_token = None
    save_error = ""
    save_filename = ""
    form = ValidationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        result = process(form.cleaned_data)
        if result.valid:
            if result.tumbling_name:
                try:
                    save_filename = result_filename(result.tumbling_name)
                    save_token = store_comparison_snapshot(result.tumbling_name, result.results)
                except CsvServiceError as error:
                    save_error = str(error)
            else:
                save_error = "Unable to save results because the Tumbling name could not be identified."
    return render(
        request,
        "validatesap/index.html",
        {
            "form": form,
            "result": result,
            "save_token": save_token,
            "save_error": save_error,
            "save_filename": save_filename,
        },
    )


@require_POST
def save_results(request):
    token = request.POST.get("result_token", "")
    action = request.POST.get("action", "save")
    snapshot = load_comparison_snapshot(token)
    if snapshot is None:
        return render(
            request,
            "validatesap/save_status.html",
            {"saved": False, "message": "The comparison result is missing or has expired. Run validation again before saving."},
            status=400,
        )

    tumbling_name = snapshot.get("tumbling_name", "")
    comparison_results = snapshot.get("comparison_results")
    if action == "cancel":
        return render(
            request,
            "validatesap/save_status.html",
            {"saved": False, "cancelled": True, "message": "Save cancelled. The existing CSV was not changed."},
        )

    try:
        path = save_results_csv(
            tumbling_name,
            comparison_results,
            overwrite=action == "overwrite",
        )
    except ResultsFileExistsError as error:
        return render(
            request,
            "validatesap/save_confirm.html",
            {"filename": error.filename, "result_token": token},
        )
    except CsvServiceError as error:
        return render(
            request,
            "validatesap/save_status.html",
            {"saved": False, "message": str(error)},
            status=400,
        )

    return render(
        request,
        "validatesap/save_status.html",
        {
            "saved": True,
            "message": "Results saved successfully.",
            "filename": path.name,
            "tumbling_name": path.stem,
        },
    )


def validation_history(request):
    query = request.GET.get("q", "").strip()
    try:
        validations = filter_saved_validations(list_saved_validations(), query)
        error = ""
    except CsvServiceError as service_error:
        validations = []
        error = str(service_error)
    return render(
        request,
        "validatesap/history.html",
        {"validations": validations, "history_error": error, "history_query": query},
    )


def historical_validation_detail(request, tumbling_name):
    try:
        validation = load_results_csv(tumbling_name)
    except SavedValidationNotFoundError as error:
        return render(request, "validatesap/history_error.html", {"message": str(error)}, status=404)
    except (InvalidSavedValidationError, CsvServiceError) as error:
        message = "Unable to load this saved validation because the CSV file is invalid or incomplete."
        if not isinstance(error, InvalidSavedValidationError):
            message = str(error)
        return render(request, "validatesap/history_error.html", {"message": message}, status=422)
    return render(request, "validatesap/history_detail.html", {"validation": validation})
