"""Domain filtering constants used across Matcha Finder.

`EXCLUDE_SITES` is used when building Google Custom Search queries to remove
common noise domains. `BLOCK_DOMAINS` is consulted when crawling pages to avoid
following or normalizing links from known non-target hosts.

When logs reveal new noisy domains, append them to the appropriate list below
and keep the lists alphabetized for easier maintenance.
"""

# Google CSEで除外したいノイズドメイン
EXCLUDE_SITES = [
    # SNS / UGC / メディア
    "instagram.com", "tiktok.com", "reddit.com", "pinterest.com",
    "linkedin.com", "x.com", "quora.com", "flickr.com", "goodreads.com",
    "timeout.com", "eater.com", "theinfatuation.com", "sfchronicle.com",
    "sacbee.com", "king5.com", "thenewstribune.com", "wanderlog.com",
    "trip.com", "lemon8-app.com",
    # デリバリー / モール / 求人 / 注文ホスティング等
    "yelp.com", "ubereats.com", "doordash.com", "postmates.com",
    "seamless.com", "grubhub.com", "mercato.com", "order.online",
    "toasttab.com", "toast.site", "orderexperience.net", "appfront.app",
    "res-menu.com", "craverapp.com", "square.site", "mapquest.com",
    "indeed.com", "glassdoor.com", "rockefellercenter.com",
    "tysonscornercenter.com", "westfield.com",
    # 量販 / EC / ティーブランド等
    "amazon.com", "walmart.com", "samsclub.com", "sayweee.com",
    "centralmarket.com", "uwajimaya.com", "jadeleafmatcha.com",
    "isshikimatcha.com", "cuzenmatcha.com", "senbirdtea.com",
    # チェーン店
    "starbucks.com", "starbucksreserve.com", "bluebottlecoffee.com",
    "peets.com", "dutchbros.com", "arabicacoffeeus.com",
    "85cbakerycafe.com", "parisbaguette.com", "lalalandkindcafe.com",
    "nanasgreentea.com", "nanasgreenteaus.com", "chachamatcha.com",
    "kettl.co", "matchaful.com",
]

# クロール時に無視するドメイン
BLOCK_DOMAINS = {
    "yelp.com", "m.yelp.com", "ubereats.com", "doordash.com", "grubhub.com", "seamless.com",
    "opentable.com", "resy.com", "sevenrooms.com", "tripadvisor.com", "pinterest.com",
    "facebook.com", "m.facebook.com", "instagram.com", "tiktok.com", "reddit.com", "vogue.com",
    "theinfatuation.com", "eater.com", "la.eater.com", "ny.eater.com", "toasttab.com", "square.site",
    "linktr.ee", "google.com", "maps.google.com", "order.online", "order.alfred.la",
    "vivinavi.com", "vividnavigation.com", "uber.com", "pos.chowbus.com", "chowbus.com",
    "fantuanorder.com", "appfront.app", "mapquest.com", "linkedin.com", "x.com", "amazon.com",
    "walmart.com", "lemon8-app.com", "rockefellercenter.com", "tysonscornercenter.com", "westfield.com",
}
