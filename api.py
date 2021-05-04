from flask import Flask, abort, request, jsonify
from flask_cors import CORS
from http import HTTPStatus
from db.db_models import Opinion
from graph.citation_network import CitationNetwork
from playhouse.shortcuts import model_to_dict
from helpers import model_list_to_json
from graph.case_search import CaseSearch

app = Flask(__name__)
CORS(app)
citation_graph = CitationNetwork()


@app.after_request
def configure_caching(response: Flask.response_class):
    response.cache_control.max_age = 300
    return response


# TODO: All of these /cases/ routes can be refactored into their own Flask blueprint
@app.route('/cases/<int:resource_id>')
def get_case(resource_id: int):
    try:
        opinion = Opinion.get(resource_id=resource_id)
        return model_to_dict(opinion)
    except Opinion.DoesNotExist:
        abort(HTTPStatus.NOT_FOUND)


@app.route('/cases/similar')
def similar_cases_to_group():
    case_resource_ids = request.args.getlist('cases')
    if len(case_resource_ids) < 1:
        return "You must provide at least one case ID.", HTTPStatus.UNPROCESSABLE_ENTITY
    similar_case_query = citation_graph.similarity.db_case_similarity(tuple(case_resource_ids))
    similar_cases = [similarity_record.opinion_b for similarity_record in similar_case_query]
    return model_list_to_json(similar_cases)


@app.route('/cases/search')
def search():
    search_query = request.args.get('query')
    max_cases = request.args.get('max_cases')
    if search_query is None or len(search_query) == 0:
        return jsonify([])
    search_results = CaseSearch.search_cases(search_query, max_cases=max_cases)
    return model_list_to_json(search_results)