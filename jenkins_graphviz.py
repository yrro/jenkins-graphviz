#!/usr/bin/python

from __future__ import print_function

import argparse
import itertools
import json
import string
import urllib
import urllib2
import urlparse
import sys

import lxml.objectify

dot_template = '''
digraph {
    graph [rankdir="LR",fontsize=9,fontname="Sans"]
    node [fontname="Sans",fontsize=9]

    $repos
    $trigger_edges

    subgraph cluster_view {
        label = "$view_name"
        $view_jobs
    }
    $other_jobs
    $subproject_edges
    $pipeline_edges
}
'''

def view_url(base, view):
    '''
    >>> view_url('http://server/', '')
    'http://server/'
    >>> view_url('http://server/', 'All')
    'http://server/view/All/'
    >>> view_url('http://server/', 'With Space')
    'http://server/view/With%20Space/'
    >>> view_url('http://server', 'missing_slash')
    'http://server/view/missing_slash/'

    '''
    return urlparse.urljoin(base, 'view/{0}/'.format(urllib.quote(view)) if view else '')

def api_fetch(url):
    url = urlparse.urljoin(url, 'api/json')
    return json.load(urllib2.urlopen(url))

def main():
    parser = argparse.ArgumentParser(description='Output a Graphviz graph based on relationships between Jenkins jobs')
    parser.add_argument('server', help='URL of Jenkins server')
    parser.add_argument('--view', '-v', help='Filter jobs by view')
    args = parser.parse_args()

    view_jobs = {}
    other_jobs = {}
    pipeline_edges = set()
    subproject_edges = set()
    repos = set()
    trigger_edges = set()

    url = view_url('http://hades:8081/', args.view)
    for job in api_fetch(url)['jobs']:
        view_jobs[job['name']] = job

    # Downstreams are when a job uses the 'build other projects' post-build action
    for job in view_jobs.values():
        job_detail = api_fetch(job['url'])
        for downstream in job_detail['downstreamProjects']:
            pipeline_edges.add ((job['name'], downstream['name']))
            if downstream['name'] not in view_jobs:
                other_jobs[downstream['name']] = downstream
        for upstream in job_detail['upstreamProjects']:
            pipeline_edges.add ((upstream['name'], job['name']))
            if upstream['name'] not in view_jobs:
                other_jobs[upstream['name']] = upstream

    for job in itertools.chain(view_jobs.values(), other_jobs.values()):
        job['config'] = lxml.objectify.parse(urllib2.urlopen(urlparse.urljoin(job['url'], 'config.xml')))

        job['subprojects'] = set()
        subprojects = job['config'].xpath('/*/builders/hudson.plugins.parameterizedtrigger.TriggerBuilder/configs/hudson.plugins.parameterizedtrigger.BlockableBuildTriggerConfig/projects')
        if subprojects:
            job['subprojects'].update([s.strip() for s in str(subprojects[0]).split(',')])

        for subproject in job['subprojects']:
            subproject_edges.add ((job['name'], subproject))

        job['enabled'] = not job['config'].xpath('/*/disabled')[0]

    for job in view_jobs.values():
        for repo in job['config'].xpath('/*/scm/userRemoteConfigs/hudson.plugins.git.UserRemoteConfig'):
            for branch in job['config'].xpath('/*/scm/branches/hudson.plugins.git.BranchSpec'):
                for trigger in job['config'].xpath('/*/triggers/*'):
                    if trigger.tag in ['hudson.triggers.TimerTrigger', 'hudson.triggers.SCMTrigger', 'com.cloudbees.jenkins.GitHubPushTrigger']:
                        repos.add((repo.url, branch.name))
                        trigger_edges.add(((repo.url, branch.name), job['name']))
                        break
                    print('Unknown trigger: {}', file=sys.stderr)

    print(string.Template(dot_template).substitute({
        'repos': '\n'.join(['"{0}\\n{1}" [URL="{2}",shape=tab]'.format(repo[0], repo[1], str(repo[0]).replace('git@github.com:', 'https://github.com/', 1)) for repo in repos]),
        'trigger_edges': '\n'.join(['"{0}\\n{1}" -> "{2}"'.format(repo[0], repo[1], job) for repo, job in trigger_edges]),
        'view_name': args.view if args.view else '',
        'view_jobs': '\n'.join(['"{0}" [shape="box", URL="{1}", color="{2}", fontcolor="{2}"]'.format(job['name'], job['url'], 'black' if job['enabled'] else 'grey') for name, job in sorted(view_jobs.iteritems())]),
        'other_jobs': '\n'.join(['"{0}" [shape="box", URL="{1}"]'.format(job['name'], job['url']) for name, job in sorted(other_jobs.iteritems())]),
        'pipeline_edges': '\n'.join(['"{0}" -> "{1}"'.format(a, b) for a, b in pipeline_edges]),
        'subproject_edges': '\n'.join(['"{0}" -> "{1}" [style=dotted]'.format(a, b) for a, b in subproject_edges])
    }))

if __name__ == '__main__':
    main()

# vim: ts=8 sts=4 sw=4 et
