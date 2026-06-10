import matplotlib.pyplot as plt
from datetime import datetime

class FunnelChart:

    @staticmethod
    def show_funnel(
            applications,
            assessments,
            interviews,
            rejected,
            offers,
            start_date,
            end_date):

        labels = [
            "Applications",
            "Rejected",
            "Assessments",
            "Interviews",
            "Offers"
        ]

        values = [
            applications,
            rejected,
            assessments,
            interviews,
            offers
        ]

        percentages = [
            round(v / applications * 100, 2)
            if applications > 0 else 0
            for v in values
        ]

        plt.figure(figsize=(12, 6))

        bars = plt.barh(
            labels,
            values
        )

        plt.gca().invert_yaxis()

        plt.title(
            f"JobTrack Recruitment Funnel\n"
            f"Applications from {start_date} to {end_date}"
        )
        plt.xlabel("Applications")

        for i, bar in enumerate(bars):

            if i == 0:
                label = f"{values[i]}"
            else:
                label = f"{values[i]} ({percentages[i]}%)"

            plt.text(
                bar.get_width() + 2,
                bar.get_y() + bar.get_height() / 2,
                label,
                va="center"
            )

        plt.tight_layout()
        plt.show()