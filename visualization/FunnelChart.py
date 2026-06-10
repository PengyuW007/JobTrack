import plotly.graph_objects as go


class FunnelChart:

    @staticmethod
    def export_funnel_image(applications, assessments, interviews, rejected, offers):
        no_response = applications - assessments - interviews - rejected - offers

        fig = go.Figure(data=[go.Sankey(
            node=dict(
                pad=20,
                thickness=20,
                label=[
                    f"{applications} Applications",
                    f"{assessments} Assessments",
                    f"{interviews} Interviews",
                    f"{rejected} Rejected",
                    f"{offers} Offers",
                    f"{no_response} No Answer / In Progress"
                ]
            ),
            link=dict(
                source=[0, 0, 0, 0, 0],
                target=[1, 2, 3, 4, 5],
                value=[
                    assessments,
                    interviews,
                    rejected,
                    offers,
                    no_response
                ]
            )
        )])

        fig.update_layout(
            title_text="Job Search Funnel",
            font_size=16
        )

        fig.write_image("jobtrack_funnel.png")