from unittest import mock
from urllib.parse import quote

from django.test import SimpleTestCase, override_settings
from django.urls import reverse

from . import views
from .sitemaps import StaticViewSitemap


class CareersPageTests(SimpleTestCase):
    def test_careers_page_renders_without_a_database_and_returns_200(self):
        response = self.client.get(reverse('careers'))
        self.assertEqual(response.status_code, 200)

    def test_page_is_public_when_steam_experience_is_not_public(self):
        with override_settings(STEAM_EXPERIENCE_PUBLIC=False):
            response = self.client.get(reverse('careers'))
            self.assertEqual(response.status_code, 200)
            self.assertIn('careers', StaticViewSitemap().items())

    def test_seo_meta_tags_and_page_title(self):
        response = self.client.get(reverse('careers'))
        self.assertContains(
            response,
            '<title>Careers | Mindset Coders Uganda</title>',
        )
        self.assertContains(
            response,
            '<meta name="description" content="Open roles at Mindset Coders Uganda: Associate STEM Instructors and Junior Associate, Marketing & Communications.">',
        )
        self.assertContains(
            response,
            '<meta property="og:title" content="Careers | Mindset Coders Uganda">',
        )
        self.assertContains(
            response,
            '<meta property="og:description" content="Open roles at Mindset Coders Uganda: Associate STEM Instructors and Junior Associate, Marketing & Communications.">',
        )
        self.assertContains(
            response,
            '<link rel="canonical" href="http://testserver/careers/">',
        )

    def test_careers_page_shows_headings_and_exact_role_copy(self):
        response = self.client.get(reverse('careers'))

        # Badge and headings
        self.assertContains(response, '<span class="badge">Careers</span>')
        self.assertContains(response, '<h1>We are hiring!</h1>')
        self.assertContains(response, 'Associate STEM Instructors')

        # Chips
        self.assertContains(response, 'Part-Time')
        self.assertContains(response, 'Entry-Level')
        self.assertContains(response, 'Kampala')

        # Intro and lead in
        self.assertContains(
            response,
            'Mindset Coders is expanding its team of instructors passionate about technology, education and inspiring the next generation of innovators.',
        )
        self.assertContains(
            response,
            'We are looking for enthusiastic, reliable and curious individuals interested in teaching children and young people in the following areas:',
        )

        # 4 Area cards
        for card_title in (
            'Coding and software programming',
            'Robotics and electronics',
            'Foundational STEM education',
            'Design thinking and innovation',
        ):
            self.assertContains(response, card_title)

        # Who should apply section and every list item
        self.assertContains(response, '<h2>Who should apply?</h2>')
        for item in (
            'Recent graduates and early-career professionals in STEM, computer science, engineering, IT, education or related fields.',
            'Individuals with practical technical skills and a willingness to learn.',
            'Individuals who enjoy working with children and young people.',
            'Reliable, punctual and proactive individuals with strong communication skills.',
            'Individuals available for scheduled weekday and/or weekend teaching assignments.',
        ):
            self.assertContains(response, item)

        # Note
        self.assertContains(
            response,
            'Previous teaching experience is an advantage but is not mandatory.',
        )

        # What we offer section and every list item
        self.assertContains(response, '<h2>What we offer</h2>')
        for item in (
            'Instructor training and professional development.',
            'Access to structured curricula and teaching resources.',
            'Practical experience delivering STEM education programmes.',
            'Paid teaching assignments.',
            'Opportunities for professional growth within Mindset Coders.',
        ):
            self.assertContains(response, item)

        # Paragraph and Location
        self.assertContains(
            response,
            'This is a part-time, assignment-based opportunity for individuals who are committed to learning, delivering quality work and growing with an ambitious education technology company.',
        )
        self.assertContains(response, 'Kampala, Uganda')

        # How to apply section
        self.assertContains(response, '<h2>How to apply</h2>')
        self.assertContains(
            response,
            'Send your CV and a brief introduction highlighting your technical skills, interests and availability to info@mindset-group.org.',
        )
        self.assertContains(response, 'info@mindset-group.org')
        self.assertContains(
            response,
            'Subject: Associate STEM Instructor Application',
        )
        self.assertContains(
            response,
            'Mindset Coders | BIG IDEAS START HERE',
        )

    def test_apply_button_mailto_link_and_umami_tracking(self):
        response = self.client.get(reverse('careers'))
        expected_subject = quote('Associate STEM Instructor Application')
        self.assertEqual(expected_subject, 'Associate%20STEM%20Instructor%20Application')
        expected_href = f'href="mailto:info@mindset-group.org?subject={expected_subject}"'

        self.assertContains(response, expected_href)
        self.assertContains(response, 'data-umami-event="apply-instructor"')
        self.assertContains(response, 'data-umami-event-from="careers"')
        self.assertContains(response, 'Apply by email')
        self.assertContains(response, 'id="apply"')

    def test_second_role_shows_all_copy_and_lists(self):
        response = self.client.get(reverse('careers'))

        for item in (
            'Junior Associate, Marketing &amp; Communications',
            'Full-Time',
            'Early Career',
            'Are you creative, curious and passionate about digital marketing, technology and storytelling?',
            'Mindset Coders is looking for a proactive individual to help us grow our brand, market our products and tell the stories behind our work in STEM education.',
            'What you will do',
            'Create engaging digital content, including graphics, photos and videos.',
            'Manage our social media platforms.',
            'Plan and execute marketing campaigns.',
            'Promote our products, programmes and events.',
            'Support lead generation and track marketing performance.',
            'Recent graduates and early-career professionals in Marketing, Communications, Multimedia, Business or related fields.',
            'Creative individuals with practical content creation and video editing skills.',
            'Individuals familiar with social media platforms and digital marketing tools.',
            'Strong communicators who are proactive, organised, reliable and willing to learn.',
            'Note:</strong> A strong portfolio and practical skills are highly valued.',
            'Location: Kyanja, Kampala',
            'Send your CV, a brief introduction and samples of your work to info@mindset-group.org.',
            'Subject: Marketing &amp; Communications Associate Application',
        ):
            self.assertContains(response, item)

    def test_second_role_mailto_subject_and_tracking_event(self):
        response = self.client.get(reverse('careers'))
        self.assertContains(
            response,
            'href="mailto:info@mindset-group.org?subject=Marketing%20%26%20Communications%20Associate%20Application"',
        )
        self.assertContains(response, 'data-umami-event="apply-marketing"')

    def test_open_roles_links_point_to_role_anchors(self):
        response = self.client.get(reverse('careers'))
        self.assertContains(
            response,
            '<a href="#associate-stem-instructors">Associate STEM Instructors</a>',
        )
        self.assertContains(response, 'id="associate-stem-instructors"')
        self.assertContains(
            response,
            '<a href="#marketing-communications">Junior Associate, Marketing &amp; Communications</a>',
        )
        self.assertContains(response, 'id="marketing-communications"')

    def test_open_roles_list_is_hidden_for_one_role(self):
        with mock.patch.object(views, 'CAREERS', [views.CAREERS[0]]):
            response = self.client.get(reverse('careers'))
            self.assertNotContains(response, 'class="careers-open-roles"')
            self.assertContains(response, 'Associate STEM Instructors')

    def test_commented_wide_img_slot_exists(self):
        response = self.client.get(reverse('careers'))
        self.assertContains(
            response,
            '<!-- <div class="img-slot img-slot--wide"></div> -->',
        )

    def test_footer_contains_careers_link(self):
        response = self.client.get(reverse('home'))
        self.assertContains(response, '<a href="/careers/">Careers</a>')

    def test_sitemap_lists_careers_url(self):
        sitemap = StaticViewSitemap()
        self.assertIn('careers', sitemap.items())
        self.assertEqual(sitemap.location('careers'), '/careers/')

    def test_empty_careers_list_shows_only_empty_state(self):
        with mock.patch.object(views, 'CAREERS', []):
            response = self.client.get(reverse('careers'))
            self.assertEqual(response.status_code, 200)
            self.assertContains(
                response,
                'No open roles right now. You are welcome to write to info@mindset-group.org.',
            )
            # Nothing else of the role is shown
            self.assertNotContains(response, '<h2>Associate STEM Instructors</h2>')
            self.assertNotContains(response, 'Who should apply?')
            self.assertNotContains(response, 'What we offer')
            self.assertNotContains(response, 'How to apply')
            self.assertNotContains(response, 'Coding and software programming')
            self.assertNotContains(response, 'Apply by email')
            self.assertNotContains(response, 'BIG IDEAS START HERE')
            self.assertNotContains(response, 'class="careers-open-roles"')
