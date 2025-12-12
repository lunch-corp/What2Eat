# src/utils/analytics.py

import streamlit.components.v1 as components

from config.constants import GOOGLE_ANALYTIC_ID, MICROSOFT_CLARITY_ID


def load_analytics():
    """Google Analytics와 Microsoft Clarity 스크립트를 로드합니다."""
    script = f"""
    <!-- Google tag (gtag.js) -->
    <script async src="https://www.googletagmanager.com/gtag/js?id={GOOGLE_ANALYTIC_ID}"></script>
    <script>
      window.dataLayer = window.dataLayer || [];
      function gtag(){{dataLayer.push(arguments);}}
      gtag('js', new Date());
      gtag('config', '{GOOGLE_ANALYTIC_ID}');
    </script>

    <!-- Microsoft Clarity -->
    <script type="text/javascript">
        (function(c,l,a,r,i,t,y){{
            c[a]=c[a]||function(){{(c[a].q=c[a].q||[]).push(arguments);}};
            t=l.createElement(r);t.async=1;t.src="https://www.clarity.ms/tag/"+i;
            y=l.getElementsByTagName(r)[0];y.parentNode.insertBefore(t,y);
        }})(window, document, "clarity", "script", "{MICROSOFT_CLARITY_ID}");
    </script>
    """

    components.html(script, height=0)
