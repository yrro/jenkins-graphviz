Jenkins-Graphviz
================

Requirements
------------

 * Python 2.7
 * [lxml](http://lxml.de/)

Usage example
-------------

        python jenkins_graphviz.py -v 'Some View' http://jenkins.example.com/ | dot -Tsvg > some_view.svg
