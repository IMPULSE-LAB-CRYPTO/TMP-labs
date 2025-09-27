# attribution:
# https://containersolutions.github.io/runbooks/posts/python/module-has-no-attribute/#step-2
import os
import sys
import json

# Добавляем путь к модулю для корректного импорта
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from ..first_timers import first_timers


example_res = json.load(open('data/example.json', 'r'))
example_issues = example_res['items']


def test_fetcher():
    """Test whether first_timer_issues are getting picked up."""
    issue_label = 'good first issue'
    # Тест использует параметр days_old
    new_issues = first_timers.get_first_timer_issues(issue_label, days_old=30)
    assert new_issues is not None


test_fetcher.__setattr__('__test__', False)  # Test disabled by default.


def test_get_fresh():
    """Test whether fresh issues are retrieved."""
    new_issues = first_timers.get_fresh(example_issues[:-1], example_issues)
    assert new_issues[0] == example_issues[-1]


def test_humanize_url():
    """Test whether the humanization of api endpoint works.
    Please see https://en.wikipedia.org/wiki/URI_normalization
    """

    api_url = "https://api.github.com/repos/tidusjar/NZBDash/issues/53"
    human_url = 'https://github.com/tidusjar/NZBDash/issues/53'
    assert first_timers.humanize_url(api_url) == human_url


def test_humanize_url_with_api_version():
    """Test humanize_url with versioned API endpoint."""
    api_url = "https://api.github.com/v3/repos/tidusjar/NZBDash/issues/53"
    human_url = 'https://github.com/tidusjar/NZBDash/issues/53'
    assert first_timers.humanize_url(api_url) == human_url


def test_humanize_url_invalid():
    """Test humanize_url with invalid URL."""
    api_url = "https://invalid-url.com/repos/test/issues/1"
    try:
        first_timers.humanize_url(api_url)
        assert False, "Should have raised ValueError"
    except ValueError:
        assert True  # Ожидаемое поведение