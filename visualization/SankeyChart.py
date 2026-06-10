import matplotlib.pyplot as plt
from matplotlib.sankey import Sankey


class SankeyChart:

    @staticmethod
    def show_sankey(
            applications,
            assessments,
            interviews,
            rejected,
            offers):

        in_progress = max(
            applications - assessments - interviews - rejected - offers,
            0
        )

        fig = plt.figure(figsize=(12, 7))
        ax = fig.add_subplot(1, 1, 1)

        sankey = Sankey(
            ax=ax,
            scale=1.0 / applications if applications > 0 else 1,
            offset=0.25,
            head_angle=120,
            margin=0.3
        )

        sankey.add(
            flows=[
                applications,
                -assessments,
                -interviews,
                -rejected,
                -offers,
                -in_progress
            ],
            labels=[
                f"Applications\n{applications}",
                f"Assessments\n{assessments}",
                f"Interviews\n{interviews}",
                f"Rejected\n{rejected}",
                f"Offers\n{offers}",
                f"In Progress\n{in_progress}"
            ],
            orientations=[
                0,
                1,
                1,
                -1,
                -1,
                0
            ],
            facecolor="#A5D6A7",
            edgecolor="#1B5E20",
            linewidth=1.5
        )

        diagrams = sankey.finish()

        for diagram in diagrams:
            for text in diagram.texts:
                text.set_fontsize(10)

        ax.set_title(
            "JobTrack Sankey Diagram",
            fontsize=16,
            fontweight="bold"
        )

        ax.axis("off")
        plt.tight_layout()
        plt.show()