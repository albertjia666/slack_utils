# -*- coding:utf-8 -*-
import mcs_config
from jira import JIRA
from slack_sdk import WebClient
from apscheduler.schedulers.blocking import BlockingScheduler
import datetime
import json
import urllib3
urllib3.disable_warnings()
from mcs_logger import Log

log = Log(file_name=None, log_name='mcs.log').init_logger()

BOT_TOKEN = "xoxb-xxx-xxxx-xxxx"  # noc-jira-update
slack_bot_handle = WebClient(token=BOT_TOKEN, ssl=mcs_config.ssl_context)


def get_user_slack_id(userid):

    log.info("[GET_USER_SLACK_ID] OF USER %s START" % userid)
    for email_suffix in ['@[company].tv', '@[company].com', '@apac.[company].com']:
        try:
            user_res = slack_bot_handle.users_lookupByEmail(
                email=userid + email_suffix
            )
        except Exception as e:
            log.error("[GET_USER_SLACK_ID] OF USER %s ERROR: %s" % (userid, str(e).replace("\n", " ")))
            continue
        else:
            log.info(f"[GET_USER_SLACK_ID] OF USER {userid} DONE: {str(user_res['user']['id'])}: {userid + email_suffix}")
            return str(user_res['user']['id']) if user_res['ok'] else None
    else:
        log.error("[GET_USER_SLACK_ID] OF USER %s NOT FOUND" % userid)


def slack_info(ticket_no, ticket_attach, userid):

    slack_key_id = get_user_slack_id(userid)

    if slack_key_id is None:
        ticket_info = json.dumps({
            "attachments": [
                {
                    "fallback": "JIRA Ticket Update Notification",
                    "title": "Problem Ticket!!! Engineer Deactivated Probably",
                    "text": 'https://jira.[company].tv/browse/%s' % ticket_no,
                    "color": "#ff0000"
                }
            ]
        })
        slack_info(ticket_no, ticket_info, 'user1')
        slack_info(ticket_no, ticket_info, 'user2')
    else:
        channel_res = slack_bot_handle.conversations_open(
            users=slack_key_id
        )
        im_channel_id = channel_res['channel']['id']
        slack_bot_handle.chat_postMessage(
            channel=im_channel_id,
            attachments=json.loads(ticket_attach)["attachments"]
        )


def slack_to_assignee(jira_handle, ticket_no):

    issue = jira_handle.issue(ticket_no)
    assignee_email = str(issue.raw['fields']['assignee']['emailAddress'])
    if assignee_email == 'noc@[company].tv':
        reporter_email = str(issue.raw['fields']['reporter']['emailAddress'])
        slack_user_id = reporter_email.split('@')[0]
    else:
        slack_user_id = assignee_email.split('@')[0]
    log.info(f"[SLACK_TO_ASSIGNEE] OF USER {slack_user_id} ON {ticket_no}")
    ticket_summary = str(issue.raw['fields']['summary'])
    slack_attach = json.dumps({
        "attachments": [
            {
                "fallback": "JIRA Ticket Update Notification",
                "title": ticket_no + ' - ' + ticket_summary,
                "title_link": 'https://jira.[company].tv/browse/%s' % ticket_no,
                "pretext": '_NOTE: These access have been revoked, please click "OPS Review" button and update the "command history(on-prem)" or "audit key(ec2)" ASAP_',
                "color": "#36a64f"
            }
        ]
    })
    slack_info(ticket_no, slack_attach, slack_user_id)


def jira_init():

    log.info(f"[JIRA_INIT] Production Access Review Start {datetime.datetime.now()}")

    jira_handle = None
    try:
        jira_handle = JIRA(
            options=mcs_config.JIRA_OPTIONS,
            basic_auth=(mcs_config.JIRA_USERNAME, mcs_config.JIRA_PASSWORD),
            timeout=60
        )

        jira_filter = 'issuetype = "Ops- Access Request" ' \
                      'AND createdDate >= "2019-06-17 00:01" ' \
                      'AND "Prod Access Platform" = IPA ' \
                      'AND summary ~ "FROM" ' \
                      'AND "Access Type" = "Read & Write" ' \
                      'AND summary ~ IPA ' \
                      'AND status = "WAITING ENG INPUT" ' \
                      'AND comment ~ "has been revoked" ' \
                      'ORDER BY created DESC'

        res = jira_handle.search_issues(jira_filter, maxResults=500)

        ticket_key_list = []
        count = 0
        for ticket in res:
            ticket_no = str(ticket.key)
            slack_to_assignee(jira_handle, ticket_no)
            ticket_key_list.append(ticket_no)
            count += 1

        if len(ticket_key_list) > 0:
            filter_url = 'https://jira.[company].tv/browse/' + str(ticket_key_list[0]) + '?' \
                         'jql=issuetype%20%3D%20%22Ops-%20Access%20Request%22%20' \
                         'AND%20createdDate%20%3E%3D%20%222019-06-17%2000%3A01%22%20' \
                         'AND%20%22Prod%20Access%20Platform%22%20%3D%20IPA%20' \
                         'AND%20summary%20~%20%22FROM%22%20' \
                         'AND%20%22Access%20Type%22%20%3D%20%22Read%20%26%20Write%22%20' \
                         'AND%20summary%20~%20IPA%20' \
                         'AND%20comment%20~%20%22has%20been%20revoked%22%20' \
                         'AND%20status%20%3D%20%22WAITING%20ENG%20INPUT%22%20ORDER%20BY%20created%20DESC'
        else:
            filter_url = 'https://jira.[company].tv/browse/OPS-55786?' \
                         'jql=issuetype%20%3D%20%22Ops-%20Access%20Request%22%20' \
                         'AND%20createdDate%20%3E%3D%20%222019-06-17%2000%3A01%22%20' \
                         'AND%20status%20%3D%20%22WAITING%20ENG%20INPUT%22%20AND%20reporter%20%3D%20noc%20' \
                         'AND%20%22Access%20Type%22%20%3D%20%22Read%20%26%20Write%22%20' \
                         'AND%20comment%20~%20%22has%20been%20revoked%22%20'

        ticket_key_string = "\n".join(ticket_key_list)

        if ticket_key_list:

            ticket_info = json.dumps({
                "attachments": [
                    {
                        "fallback": "JIRA Ticket Update Notification",
                        "title": " Ticket Need Update",
                        "title_link": filter_url,
                        "text": ticket_key_string,
                        "pretext": "_%d Ticket Need Update_" % count,
                        "color": "#36a64f"
                    }
                ]
            })

            slack_info('NA', ticket_info, 'user1')
            slack_info('NA', ticket_info, 'user2')

        else:
            ticket_info = json.dumps({
                "attachments": [
                    {
                        "fallback": "JIRA Ticket Update Notification",
                        "title": " Ticket Need Update",
                        "title_link": filter_url,
                        "text": 'No Ticket Need Update',
                        "pretext": "_%d Ticket Need Update_" % 0,
                        "color": "#36a64f"
                    }
                ]
            })

            slack_info('NA', ticket_info, 'user1')
            slack_info('NA', ticket_info, 'user2')

        log.info(f"[JIRA INIT] Production Access Review End {datetime.datetime.now()}")

    except Exception as e:
        log.error("[JIRA INIT] ERROR: %s" % str(e).replace('\n', ' '))
    finally:
        if jira_handle is not None:
            jira_handle.close()


def runner():

    scheduler = None
    try:
        scheduler = BlockingScheduler()
        scheduler.add_job(jira_init, 'cron', day_of_week="1,3", hour=2, minute=1, jitter=30)
        scheduler.start()
    except Exception as e:
        log.error("[WATCHER] ERROR %s" % str(e))
    finally:
        if scheduler is not None:
            scheduler.shutdown()


if __name__ == '__main__':

    runner()
