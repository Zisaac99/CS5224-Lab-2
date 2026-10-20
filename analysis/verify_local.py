"""Pure-Python cross-check of follower/followee counts (no Spark).

Applies the same cleaning rules as follow_counts.py so the numbers can be
compared with the Spark output produced on EMR Serverless.

Usage: python analysis/verify_local.py [path] [user_id ...]
"""
import sys

DEFAULT_USERS = ["214328887", "107830991"]


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "twitter_combined.txt"
    users = sys.argv[2:] or DEFAULT_USERS

    raw = malformed = self_loops = 0
    edges = set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            raw += 1
            parts = line.split()
            if len(parts) != 2 or not all(p.isdigit() for p in parts):
                malformed += 1
                continue
            follower, followee = int(parts[0]), int(parts[1])
            if follower == followee:
                self_loops += 1
                continue
            edges.add((follower, followee))

    followers, followees = {}, {}
    for a, b in edges:
        followees[a] = followees.get(a, 0) + 1
        followers[b] = followers.get(b, 0) + 1

    print(f"raw lines        : {raw}")
    print(f"malformed lines  : {malformed}")
    print(f"self-loop lines  : {self_loops}")
    print(f"unique edges     : {len(edges)}")
    print(f"users            : {len(followers.keys() | followees.keys())}")
    print()
    for u in users:
        uid = int(u)
        print(f"{u} has {followers.get(uid, 0)} followers")
        print(f"{u} has {followees.get(uid, 0)} followees")


if __name__ == "__main__":
    main()
