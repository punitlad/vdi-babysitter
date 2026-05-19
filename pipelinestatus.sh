#!/bin/bash

CI=$(gh run list --json name,startedAt,updatedAt,conclusion,url --workflow ci.yml --limit 1 | jq .[])
RELEASE=$(gh run list --json name,startedAt,updatedAt,conclusion,url --workflow release.yml --limit 1 | jq .[])

echo $CI
echo $RELEASEi 