# glossary

## f1 scheduled sync

### *cron*
cron expression with 5 or 6 fields

## f2 search

### *search host*
external index server host

### *files*
dir of user files

### *derived*
dir /w subdirs *hashes* & *paths*

### *hashes*
dir /w *files* unique *meta* subdirs

### *paths*
dir /w 1-1 symlink *files* relpaths to *meta*

### *meta*
per hash named dir w/ derived metadata files
  * *doc*
  * *meta log*

### *doc*
main *meta* file for *search host* w/ fields
  * `id`: file hash
  * `type`: file MIME type
  * `size`: file size in bytes
  * `paths`: obj of relpaths to *epoch4*
  * `copies`: total paths
  * `mtime`: greatest paths mtime in *epoch4*
  * `archive`: is any path in *archive*?
  * `online`: is any path mounted?
  * `next`: next pending *deriver host* name

### *meta log*
logs any changes to *meta*

### *epoch4*
epoch secs truncated to 4 decimals for search

### *pilot*
first index run output dir

### *filter*
search host filter param

### *sort*
search host sort param

## f3 removable drives

### *archive*
dir for temp mounting removable media

## f4 derivers

### *queue host*
external synchronized queue host

### *deriver host*
external read-only file processing server w/
  * `host`: *queue host* address
  * `queue`: target *goal queue*
  * `uid`: home-index id
  * `timeout`: max runtime per file in secs
  * `check`: does this file need run?
  * `run`: do 1 file from queue
  * `load?`: load after get locks
  * `unload?`: unload before yield locks
  * `locks?`: list of needed locks
> `?`= optional

## f5 chunk search

### *chunk*
file segment

### *concept*
meaning vector for *chunk*

## f6 remote ops

### *api*
remote request interface

