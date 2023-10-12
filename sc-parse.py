from SwimScraper import SwimScraper as ss

s = ss.getRoster(
    team_ID=10009146, team="Great Hearts Monte Vista", year=2023, gender="M"
)

print(s)
