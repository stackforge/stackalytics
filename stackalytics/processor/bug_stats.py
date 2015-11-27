#!/usr/bin/env python

# Copyright 2011 Thierry Carrez <thierry@openstack.org>
# Copyright 2015 Markus Zoeller <mzoeller@de.ibm.com>
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import simplejson as json
import os
import sys
from launchpadlib.launchpad import Launchpad


class BugStat(object):
    """ Represents a single value for a specific metric """

    def __init__(self, key_name, stats_value):
        self.key_name = key_name
        self.stats_value = stats_value

    def __str__(self):
        return "%s: %s" % (self.key_name, self.stats_value)

    def __repr__(self):
        return str(self)


class BugStatsCollector(object):
    """ Collect bug stats by project name ("Nova", "Cinder", ...)
    """

    LP_IMPORTANCES = ["Undecided", "Wishlist", "Low", "Medium", "High",
                      "Critical"]

    LP_OPEN_STATUSES = ["New", "Incomplete", "Confirmed",
                        "Triaged", "In Progress"]

    LP_CLOSED_STATUS = ["Fix Committed", "Fix Released", "Invalid",
                        "Won't Fix", "Opinion"]

    def __init__(self, project_name):
        self.project_name = project_name

        cachedir = os.path.expanduser("~/.launchpadlib/cache/")
        if not os.path.exists(cachedir):
            os.makedirs(cachedir, 0700)
        launchpad = Launchpad.login_anonymously('bugstats', 'production',
                                                cachedir)
        self.project = launchpad.projects[self.project_name]

    def get_open_by_importance(self):
        """ Return the stats for open bugs, separated by importance.

        :rtype: list of BugStat
        """
        importance_stats = []
        for importance in BugStatsCollector.LP_IMPORTANCES:
            bug_tasks = self.project.searchTasks(
                            status=BugStatsCollector.LP_OPEN_STATUSES,
                            importance=importance,
                            omit_duplicates=True)
            stats_key = self._get_valid_stat_key_name(importance)
            stats_value = self._count_bug_tasks(bug_tasks)
            stat = BugStat(stats_key, stats_value)
            importance_stats.append(stat)
        return importance_stats

    def get_stats_open_by_status(self):
        """ Return the stats for open bugs, separated by status.

        :rtype: list of BugStat
        """
        status_stats = []
        for status in BugStatsCollector.LP_OPEN_STATUSES:
            bug_tasks = self.project.searchTasks(
                                status=status,
                                omit_duplicates=True)
            stats_key = self._get_valid_stat_key_name(status)
            stats_value = self._count_bug_tasks(bug_tasks)
            stat = BugStat(stats_key, stats_value)
            status_stats.append(stat)
        return status_stats

    def get_stats_new_by_tag(self):
        """ Return the stats for 'New' bugs, separated by tags.

        :rtype: list of BugStat
        """
        tag_stats = []
        bug_tasks = self.project.searchTasks(
                status=["New"],
                omit_duplicates=True)
        tags_counter = {}
        for task in bug_tasks:
            try:
                tags = task.bug.tags
                if not tags:
                    tags = ["none"]
                for tag in tags:
                    if tag in tags_counter:
                        tags_counter[tag] += 1
                    else:
                        tags_counter[tag] = 1
            except TypeError, e:
                print "ignore task %s because %s" % (task.bug.id, e)
        for tag in tags_counter:
            stats_key = self._get_valid_stat_key_name(tag)
            stats_value = tags_counter[tag]
            stat = BugStat(stats_key, stats_value)
            tag_stats.append(stat)

        def add_stats_to_reset():
            file_name = "%s_tag_list.txt" % self.project_name
            with open(file_name, 'w+') as f:
                tags_list = [line.rstrip('\n') for line in f]
                for t in tags_list:
                    if t not in tags_counter.keys():
                        # explicitly set a once collected stat back to zero
                        tag_stats.append(BugStat(t, 0))
                for s in tags_counter.keys():
                    # save the tags from the current run to use in the next run
                    f.write(s + '\n')

        # (markus_z) I don't know how to tell that a once collected metric
        # should be reset to zero to avoid that the last current gets
        # flushed by statsd
        add_stats_to_reset()

        return tag_stats

    def get_not_in_progress_by_importance(self):
        """ Return the stats for bugs which are not yet in progress, separated
            by importance.

        :rtype: list of BugStat
        """
        importance_stats = []
        for importance in BugStatsCollector.LP_IMPORTANCES:
            bug_tasks = self.project.searchTasks(
                status=["New", "Incomplete", "Confirmed", "Triaged"],
                importance=importance,
                omit_duplicates=True)
            stats_key = self._get_valid_stat_key_name(importance)
            stats_value = self._count_bug_tasks(bug_tasks)
            stat = BugStat(stats_key, stats_value)
            importance_stats.append(stat)
        return importance_stats

    def _get_valid_stat_key_name(self, name):
        stat_key = name
        stat_key = stat_key.replace(" ", "").lower()
        stat_key = stat_key.replace("(", "-")
        stat_key = stat_key.replace(")", "")
        return stat_key

    def _count_bug_tasks(self, bug_tasks):
        return int(bug_tasks._wadl_resource.representation['total_size'])


class BugStatsPusher(object):
    """ Pushed BugStat objects to a specific target """

    def __init__(self, metric_name, target="statsd"):
        self.target = target
        self.metric_name = metric_name

        if target == "statsd":
            import statsd
            self.gauge = statsd.Gauge(self.metric_name)

    def to_target(self, bug_stats):
        """ Pushes the given list of BugStat objects to the target

        :param bug_stats: list of BugStat objects to push
        """
        for bug_stat in bug_stats:
            if self.target == "statsd":
                self.gauge.send(bug_stat.key_name, bug_stat.stats_value)
            if self.target == "syso":
                print(bug_stat)


if __name__ == '__main__':
    base_path = os.path.dirname(sys.argv[0])
    config_path = os.path.join(base_path, "bug_stats_config.js")
    if not os.path.isfile(config_path):
        msg = '%s does not contain bug_stats_config.js' % base_path
        print >> sys.stderr, msg
        sys.exit(1)

    with open(config_path, 'r') as configfile:
        config = json.load(configfile)
    projects = config['projects']

    for p in projects:
        project_name = p['project']
        collector = BugStatsCollector(project_name)
        # TODO(markus_z) Right now it's just showing what it *would* push
        # to statsd
        target_name = "syso"

        pusher = BugStatsPusher('launchpad.bugs.%s.open-by-importance'
                                % project_name, target=target_name)
        pusher.to_target(collector.get_open_by_importance())

        pusher = BugStatsPusher('launchpad.bugs.%s.open-by-status'
                                % project_name, target=target_name)
        pusher.to_target(collector.get_stats_open_by_status())

        pusher = BugStatsPusher('launchpad.bugs.%s.not-inprogress-by-importance'
                                % project_name, target=target_name)
        pusher.to_target(collector.get_not_in_progress_by_importance())

        pusher = BugStatsPusher('launchpad.bugs.%s.new-by-tag'
                                % project_name, target=target_name)
        pusher.to_target(collector.get_stats_new_by_tag())

