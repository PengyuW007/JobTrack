import plotly.graph_objects as go


class FunnelChart:

    @staticmethod
    def export_funnel_image(applications, assessments, interviews, rejected, offers):
        stages = [
            "Applications",
            "Rejected",
            "Assessments",
            "Interviews",
            "Offers"
        ]

        values = [
            applications,
            rejected,
            interviews,
            assessments,
            offers
        ]

        fig = go.Figure(
            go.Bar(
                x=values,
                y=stages,
                orientation="h",
                text=[
                    f"{values[i]} ({round(values[i] / applications * 100, 2)}%)"
                    for i in range(len(values))
                ],
                textposition="outside",
                marker=dict(
                    color=[
                        "#1B5E20",
                        "#C62828",
                        "#2E7D32",
                        "#388E3C",
                        "#1565C0"
                    ]
                )
            )
        )

        fig.update_layout(
            title="JobTrack Recruitment Funnel",
            xaxis_title="Count",
            yaxis_title="",
            yaxis=dict(autorange="reversed"),
            width=1200,
            height=700,
            paper_bgcolor="white",
            plot_bgcolor="white",
            font=dict(size=18),
            margin=dict(l=180, r=120, t=100, b=80)
        )

        fig.write_image("jobtrack_funnel.png", scale=2)