# -*- coding: utf-8 -*-
import re
from datetime import datetime
import requests
import tweepy
import logging
from typing import List, Dict, Any, Optional

# Set up logging
logging.basicConfig(filename='app.log', level=logging.INFO)


DAYS_OLD = 15
MAX_TWEETS_LEN = 280
ELLIPSIS = u'…'
GITHUB_API_BASE = 'https://api.github.com/search/issues'
FIRST_ISSUE_QUERY_URL = GITHUB_API_BASE + '?q=label:"{}"+is:issue+is:open&sort=updated&order=desc'
TWITTER_SHORT_URL_LENGTH = 30


# Logging helper function
def log_info(message):
    logging.info(message)


def log_warning(message):
    logging.warning(message)


def log_error(message):
    logging.error(message)


def humanize_url(api_url: str) -> str:
    """Make an API endpoint to a Human endpoint."""
    # Более надежный способ через разбор URL вместо регулярки
    try:
        # Разбираем URL на компоненты
        from urllib.parse import urlparse
        parsed_url = urlparse(api_url)

        # Извлекаем путь и разбиваем на части
        path_parts = parsed_url.path.strip('/').split('/')

        # Ожидаемый формат: /repos/owner/repo/issues/number
        if len(path_parts) >= 5 and path_parts[0] == 'repos' and path_parts[3] == 'issues':
            user, repo, issue_num = path_parts[1], path_parts[2], path_parts[4]
            return f'https://github.com/{user}/{repo}/issues/{issue_num}'
        else:
            raise ValueError(f'Unexpected API URL format: {api_url}')
    except Exception as e:
        # Fallback на регулярное выражение для обратной совместимости
        match = re.match(
            r'https://api\.github\.com/repos/([^/]+)/([^/]+)/issues/([0-9]+)', api_url)
        if not match:
            raise ValueError(f'Format of API URLs has changed: {api_url}')
        user, repo, issue_num = match.group(1, 2, 3)
        return f'https://github.com/{user}/{repo}/issues/{issue_num}'


def get_first_timer_issues(issue_label: str, days_old: int = DAYS_OLD) -> List[Dict[str, Any]]:
    """Fetches the first page of issues with the label first-timers-label
    which are still open.
    """
    res = requests.get(FIRST_ISSUE_QUERY_URL.format(issue_label))
    res.raise_for_status()

    items = [item for item in res.json()['items']
             if check_days_passed(item['created_at'], days_old)]

    return items


def check_days_passed(date_created: str, days: int) -> bool:
    created_at = datetime.strptime(date_created, "%Y-%m-%dT%H:%M:%SZ")
    return (datetime.now() - created_at).days < days


def add_repo_languages(issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Adds the repo languages to the issues list."""
    for issue in issues:
        # Инициализируем пустой список языков на случай ошибки
        issue.setdefault('languages', {})

        query_languages = issue['repository_url'] + '/languages'
        res = requests.get(query_languages)
        if res.status_code == 403:
            log_warning('Rate limit reached getting languages')
            # Продолжаем обработку, но без языков для всех issue
            continue
        if res.ok:
            issue['languages'] = res.json()
        else:
            log_warning(f'Could not handle response: {res.status_code} from the API. URL: {query_languages}')
            # Оставляем пустой словарь языков
    return issues


def get_fresh(old_issue_list: List[Dict[str, Any]], new_issue_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Returns which issues are not present in the old list of issues."""
    old_urls = {x['url'] for x in old_issue_list}
    return [x for x in new_issue_list if x['url'] not in old_urls]


def tweet_issues(issues: List[Dict[str, Any]], creds: Dict[str, str], debug: bool = False,
                 max_tweet_len: int = MAX_TWEETS_LEN) -> List[Dict[str, Any]]:
    """Takes a list of issues and credentials and tweets through the account
    associated with the credentials.
    Also takes a parameter 'debug', which can prevent actual tweeting.
    Returns a list of tweets.
    """
    if len(issues) == 0:
        return []

    auth = tweepy.OAuthHandler(creds['Consumer Key'], creds['Consumer Secret'])
    auth.set_access_token(creds['Access Token'], creds['Access Token Secret'])
    api = tweepy.API(auth)

    # Получаем актуальную длину коротких URL из Twitter API
    try:
        conf = api.configuration()
        url_len = conf['short_url_length_https']
    except Exception as e:
        log_warning(f'Could not get Twitter configuration, using default: {e}')
        url_len = TWITTER_SHORT_URL_LENGTH

    base_hashtags = u"#github"

    # 1 space with URL and 1 space before hashtags.
    allowed_title_len = max_tweet_len - (url_len + 1) - (len(base_hashtags) + 1)

    tweets = []

    for issue in issues:
        # Для каждого issue создаем копию хештегов
        current_hashtags = base_hashtags
        title = issue['title']

        if len(title) > allowed_title_len:
            title = title[: allowed_title_len - 1] + ELLIPSIS
        else:
            if 'languages' in issue and issue['languages']:
                language_hashtags = ''.join(
                    f' #{lang}' for lang in issue['languages']
                )
                current_hashtags += language_hashtags

            max_hashtags_len = max_tweet_len - (url_len + 1) - (len(title) + 1)

            if len(current_hashtags) > max_hashtags_len:
                current_hashtags = current_hashtags[:max_hashtags_len - 1] + ELLIPSIS

        url = humanize_url(issue['url'])

        try:
            tweet = f'{title} {url} {current_hashtags}'

            if not debug:
                api.update_status(tweet)

            tweets.append({
                'error': None,
                'tweet': tweet
            })

            log_info(f'Tweeted issue: {issue["title"]}')
        except Exception as e:
            tweets.append({
                'error': e,
                'tweet': tweet
            })

            log_error(f'Error tweeting issue: {issue["title"]}')
            log_error(f'Error message: {str(e)}')

    return tweets


def limit_issues(issues: List[Dict[str, Any]], limit_len: int = 100000) -> List[Dict[str, Any]]:
    """Limit the number of issues saved in our DB."""
    sorted_issues = sorted(issues, key=lambda x: x['updated_at'], reverse=True)
    return sorted_issues[:limit_len]