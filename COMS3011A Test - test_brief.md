## COMS3011A Test

## Brendan Griffiths

## Contents

## 1 Overview

Time: 2.5 Hours

Submission: URL to a public repository

Git repositories tend to be very opaque to understanding. Git does not make it easy to understand how a

repo has evolved, who has had the most impact where, and what parts o the project are the most volatile.

Your project manager has asked you to build a Repo Analysis Tool (RAT) that measures specic metrics

o a provided repository. You need to calculate these metrics or: each developer (called an author), each le, each directory, and the entire repository. These metrics are provided below.

The RAT should be a web-app dashboard or multiple repositories. This dashboard should be lterable

- A repository

- An author

- A le or directory

- Commits

- a specied period o time

- or a manually selected list o commits

It accepts a repository in two orms:

- 1. A zip le o the repo with the .git le or directory

- 2. A remote repository URL that is then deeply cloned

by:


Not every commit will have the same author, even i they were made by the same person. To address this git provides a .mailmap to merge dierent email addresses, the RAT should be able to merge authors using the mailmap. I no mailmap is provided, a user should still be able to merge dierent authors manually.

The ull list o eatures are:

- Repository Upload: Zip and Clone URL

- Multiple Repository Support

- Author Merging

- Metric Categories:

- File Metrics

- Directory Metrics

- Repository Metrics

- Commit Set Metrics

Note: Not all eatures are necessary. Please review the rubric to understand what is needed.

## 2 Metrics

A commit  has the ollowing properties

- A single author [] afer author merging

- A previous commit []

- The initial commit has [] = ∅, an empty commit

- A committer date [committer-date]

- [] is the set o all les

- Binary files are not measured

- Git provides a denition and detection o binary les

- [] is the set o all directories

- An object  ∈ [] ∪ [] is identied by its path

- Rename detection is enabled with a threshold o 50%, so just renaming a le should not change its metrics.

- Making a change and renaming an object should only have the changes impact its associated metrics.

- These changes are attributed to its new path

- I an object is deleted (it does not exist in h hip] the necessary metrics (lines removed) on its path.  but does in []), it should be recorded as a change in

The set ̄ is the set o non-merge commits reachable rom a specied reerence commit  (typically

HEAD)

- A commit set  is a subset o ̄

- The commit set  is the commit history rom UNIX timestamp  to present

H

- The commit set  is the commit history rom timestamp  inclusive until timestamp  exclusive

H


- [] is the set o all les in the repository

- [] is the set o all directories (including the root) or the commit set.

fh

## 2.1 File Metrics

- File Added Lines: The number o lines added on le  rom a commit  to the previous commit

- File Removed Lines: The number o lines removed on le  rom a commit  to the previous commit

- File Growth: The change in number o lines on le  rom a commit  to the previous commit

- File Churn: The number o changed lines on le  rom a commit  to the previous commit

## 2.2 Directory Metrics

An immediate object is an object that is directly below the specied directory

foo/

bar.txt -- immediate child of foo

baz/

beef.py -- immediate child of baz dead.py -- immediate child of baz

A le  is in a directory  at a commit  i it is in [] or [][] and is an immediate child o . Similarly or subdirectories  and [], [][].

- Directory Added Lines: The number o added lines across all immediate subdirectories  and les  in directory 

- Directory Removed Lines: The number o removed lines across all immediate subdirectories  and les  in directory 

- Directory Growth: The net growth across all immediate subdirectories  and les  in directory 

d.

-- immediate child of foo


1"7 T 1"/ +

- Directory Churn: The churn across all immediate subdirectories  and les  in directory 

3"7 T 3"/ +

## 2.3 Repository Metrics

Repository metrics are directory metrics on the root o the commit tree.

- 2.4 Commit set Metrics • Added lines over a commit set  in either a directory or le,  ∈ [] ∪[]

)": T 

- Removed lines over a commit set  in either a directory or le,  ∈ [] ∪[]

)": T 

- Growth over a commit set  in either a directory or le,  ∈ [] ∪[]

1)": T 

- Churn over a commit set  in either a directory or le,  ∈ [] ∪[]

3)": T 

- Modications: The number o commits that have at least some change on le or directory  ∈ [] ∪

 otherwise

F)": T 

- Modication requency over a le or directory  ∈ [] ∪[]

if || ≠ 

 otherwise

- Churn rate over a le or directory  ∈ [] ∪[]

 otherwise

if || ≠ 


2.5 Author Metrics We need an authorship test:

( ) ≔ 1 0 otherwise if =ℎ[]

• Author Modications on a le or directory,

 ∈ [] ∪[]

F)":"Q T –

- Author Churn on a le or directory,  ∈ [] ∪[]

3)":"Q T ‐

- Author Ownership: The raction o churn on le or directory,  ∈ [] ∪[] rom an author 

if 3)": ` B

T)":"Q T

 otherwise

## 3 Rubric

Requirements are cumulative. You can only reach a tier i the previous tier is satised. Each tier is

judged holistically.

Metric correctness is determined against a set o test repositories. Sample metrics rom each o these

repos will be provided rom a specic commit hash. These repos are open source.

- cJSON https://github.com/DaveGamble/cJSON.git

- Redis https://github.com/redis/redis.git

- Git https://github.com/git/git.git

## Provided repositories:


| Criteria Weight | ≤ 25% | ≤ 5% | ≤ 75% | d ?BB% |
| --- | --- | --- | --- | --- |
| Requirements 50% Implemented and |   | Implemented and | Implemented | Implemented all: |
|   | correct or some | correct or all | either: Filtering, | Filtering, Author |
|   | categories (repo, | metrics | Author Merge, | Merge, Multi- |
|   | le, directory, | Both: zip le and | Multi-repo | repo support |
|   | set, author) o | remote URL | support |   |
|   | metrics | ingestion |   |   |
|   | Either: zip le or |   |   |   |
|   | remote URL |   |   |   |
|   | ingestion |   |   |   |
| Architectural | 25% Redundant & | Reasonable | Efficient | Efficient |
| & UI Design | slow metric | metric | algorithms or | algorithms and |
|   | computation, | computation, | metric | architecture or |
|   | poor | okay | computation, | metric |
|   | visualisation o | visualisation o | good | computation, |
|   | metrics | metrics | visualisation o | inspired |
|   |   |   | metrics | visualisation o |
|   |   |   |   | metrics |
| Usability | 25% Poor navigation, | Okay navigation, | Good navigation, | Excellent |
|   | no error | minimal error | error handling, | navigation, good |
|   | handling, | handling, | good | perormance on |
|   | slow | okay | perormance on | large (< ?BBBBB |
|   | perormance on | perormance on | medium | commits) repos |
|   | small (< ?BBB | small | repositories, |   |
|   | commits) | repositories, | QoL eatures |   |
|   | repositories, | slow |   |   |
|   | no QoL eatures | perormance on |   |   |
|   |   | medium (∼ |   |   |
|   |   | ?BBBB commits) |   |   |
|   |   | repos, |   |   |
|   |   | minimal to none |   |   |
|   |   | QoL eatures |   |   |

AI Declaration: Claude Web (Opus 5.5) - reviewed
