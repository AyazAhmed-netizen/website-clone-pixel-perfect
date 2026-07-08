"""
Tech Stack Analyzer
技术栈分析器

功能：
- 检测前端框架（React、Vue、Angular、Svelte 等）
- 识别 UI 库和工具库
- 分析构建工具特征
- 提取样式方案（Tailwind、Bootstrap、CSS-in-JS 等）
- 解析 Meta 标签信息
"""

import re
from typing import Dict, List, Optional, Set
from playwright.async_api import Page
from .models import TechStackData, DependencyInfo


class TechStackAnalyzer:
    """
    技术栈分析器
    通过分析页面 HTML、脚本、样式来识别使用的技术栈
    """

    # 框架检测规则
    FRAMEWORK_PATTERNS = {
        "React": {
            "patterns": [
                r"react\.production\.min\.js",
                r"react-dom\.production\.min\.js",
                r"_reactRootContainer",
                r"__REACT_DEVTOOLS",
            ],
            "global_vars": ["React", "ReactDOM"],
            "data_attrs": ["data-reactroot", "data-reactid"],
        },
        "Vue": {
            "patterns": [r"vue\.js", r"vue\.min\.js", r"vue\.runtime"],
            "global_vars": ["Vue"],
            "data_attrs": ["data-v-", "v-cloak"],
        },
        "Angular": {
            "patterns": [r"angular\.js", r"angular\.min\.js", r"ng-version"],
            "global_vars": ["angular", "ng"],
            "data_attrs": ["ng-app", "ng-controller", "ng-version"],
        },
        "Svelte": {
            "patterns": [r"svelte", r"\.svelte-"],
            "global_vars": [],
            "data_attrs": ["svelte-"],
        },
        "Next.js": {
            "patterns": [r"_next/static", r"__NEXT_DATA__"],
            "global_vars": ["__NEXT_DATA__"],
            "data_attrs": ["data-next-"],
        },
        "Nuxt": {
            "patterns": [r"_nuxt/", r"__NUXT__"],
            "global_vars": ["__NUXT__"],
            "data_attrs": [],
        },
        "Gatsby": {
            "patterns": [r"gatsby-", r"___gatsby"],
            "global_vars": ["___gatsby"],
            "data_attrs": [],
        },
    }

    # UI 库检测规则
    UI_LIBRARY_PATTERNS = {
        "Bootstrap": {
            "patterns": [r"bootstrap\.css", r"bootstrap\.min\.css"],
            "classes": ["container", "row", "col-", "btn-"],
        },
        "Tailwind CSS": {
            "patterns": [r"tailwind"],
            "classes": [
                "flex",
                "grid",
                "px-",
                "py-",
                "mt-",
                "mb-",
                "text-",
                "bg-",
            ],
        },
        "Material-UI": {
            "patterns": [r"@material-ui", r"@mui"],
            "classes": ["MuiButton", "MuiBox", "MuiTypography"],
        },
        "Ant Design": {
            "patterns": [r"antd"],
            "classes": ["ant-btn", "ant-card", "ant-form"],
        },
        "Element UI": {
            "patterns": [r"element-ui"],
            "classes": ["el-button", "el-form", "el-input"],
        },
        "Chakra UI": {
            "patterns": [r"@chakra-ui"],
            "classes": ["chakra-"],
        },
    }

    # 工具库检测规则
    UTILITY_PATTERNS = {
        "jQuery": {
            "patterns": [r"jquery\.js", r"jquery\.min\.js"],
            "global_vars": ["jQuery", "$"],
        },
        "Lodash": {
            "patterns": [r"lodash\.js", r"lodash\.min\.js"],
            "global_vars": ["_"],
        },
        "Moment.js": {
            "patterns": [r"moment\.js", r"moment\.min\.js"],
            "global_vars": ["moment"],
        },
        "Day.js": {
            "patterns": [r"dayjs"],
            "global_vars": ["dayjs"],
        },
        "Axios": {
            "patterns": [r"axios\.js", r"axios\.min\.js"],
            "global_vars": ["axios"],
        },
    }

    # 构建工具检测规则
    BUILD_TOOL_PATTERNS = {
        "Webpack": {
            "patterns": [r"webpack", r"webpackJsonp", r"__webpack"],
        },
        "Vite": {
            "patterns": [r"@vite/", r"vite/"],
        },
        "Parcel": {
            "patterns": [r"parcelRequire"],
        },
        "Rollup": {
            "patterns": [r"rollup"],
        },
    }

    def __init__(self, page: Page, html_content: str):
        """
        初始化技术栈分析器

        Args:
            page: Playwright Page 对象
            html_content: 页面 HTML 内容
        """
        self.page = page
        self.html_content = html_content
        self.detected_frameworks: List[DependencyInfo] = []
        self.detected_ui_libraries: List[DependencyInfo] = []
        self.detected_utilities: List[DependencyInfo] = []
        self.detected_build_tools: List[DependencyInfo] = []
        self.features: Set[str] = set()
        self.meta_tags: Dict[str, str] = {}

    async def analyze(self) -> TechStackData:
        """
        执行完整的技术栈分析

        Returns:
            TechStackData: 技术栈分析结果
        """
        # 1. 提取 script 标签 URL
        script_urls = await self._extract_script_urls()

        # 2. 提取全局变量
        global_vars = await self._extract_global_variables()

        # 3. 提取 data 属性和 class 名
        data_attrs, class_names = await self._extract_dom_attributes()

        # 4. 检测框架
        await self._detect_frameworks(script_urls, global_vars, data_attrs)

        # 5. 检测 UI 库
        await self._detect_ui_libraries(script_urls, class_names)

        # 6. 检测工具库
        await self._detect_utilities(script_urls, global_vars)

        # 7. 检测构建工具
        await self._detect_build_tools(script_urls, self.html_content)

        # 8. 检测样式方案
        styling = await self._detect_styling(script_urls, class_names)

        # 9. 提取 Meta 标签
        await self._extract_meta_tags()

        # 10. 检测技术特征
        await self._detect_features()

        return TechStackData(
            frameworks=self.detected_frameworks,
            ui_libraries=self.detected_ui_libraries,
            utilities=self.detected_utilities,
            build_tools=self.detected_build_tools,
            styling=styling,
            features=list(self.features),
            meta_tags=self.meta_tags,
        )

    async def _extract_script_urls(self) -> List[str]:
        """
        提取页面中所有 script 标签的 URL

        Returns:
            List[str]: script URL 列表
        """
        script_urls = await self.page.evaluate("""
            () => {
                const scripts = Array.from(document.querySelectorAll('script[src]'));
                return scripts.map(s => s.src);
            }
        """)
        return script_urls or []

    async def _extract_global_variables(self) -> List[str]:
        """
        提取全局变量名称

        Returns:
            List[str]: 全局变量列表
        """
        try:
            global_vars = await self.page.evaluate("""
                () => {
                    const vars = Object.keys(window);
                    return vars.slice(0, 100);  // 限制数量避免过大
                }
            """)
            return global_vars or []
        except:
            return []

    async def _extract_dom_attributes(self) -> tuple[List[str], List[str]]:
        """
        提取 DOM 属性和类名

        Returns:
            tuple: (data 属性列表, class 名称列表)
        """
        try:
            result = await self.page.evaluate("""
                () => {
                    const dataAttrs = new Set();
                    const classNames = new Set();

                    // 遍历所有元素
                    const elements = document.querySelectorAll('*');
                    for (const el of elements) {
                        // 提取 data-* 属性
                        for (const attr of el.attributes) {
                            if (attr.name.startsWith('data-')) {
                                dataAttrs.add(attr.name);
                            }
                        }
                        // 提取 class
                        if (el.className && typeof el.className === 'string') {
                            el.className.split(/\\s+/).forEach(c => {
                                if (c) classNames.add(c);
                            });
                        }
                    }

                    return {
                        dataAttrs: Array.from(dataAttrs).slice(0, 50),
                        classNames: Array.from(classNames).slice(0, 100)
                    };
                }
            """)
            return result.get("dataAttrs", []), result.get("classNames", [])
        except:
            return [], []

    async def _detect_frameworks(
        self,
        script_urls: List[str],
        global_vars: List[str],
        data_attrs: List[str],
    ):
        """
        检测前端框架

        Args:
            script_urls: script URL 列表
            global_vars: 全局变量列表
            data_attrs: data 属性列表
        """
        all_urls_text = " ".join(script_urls)

        for name, rules in self.FRAMEWORK_PATTERNS.items():
            confidence = 0
            matched_patterns = 0

            # 检查 URL 模式
            for pattern in rules["patterns"]:
                if re.search(pattern, all_urls_text, re.IGNORECASE):
                    matched_patterns += 1
                    confidence += 30

            # 检查全局变量
            for var in rules["global_vars"]:
                if var in global_vars:
                    confidence += 25

            # 检查 data 属性
            for attr in rules["data_attrs"]:
                if any(attr in da for da in data_attrs):
                    confidence += 20

            # 如果置信度 >= 50，认为检测到该框架
            if confidence >= 50:
                self.detected_frameworks.append(
                    DependencyInfo(
                        name=name,
                        type="framework",
                        confidence=min(confidence, 100),
                    )
                )

    async def _detect_ui_libraries(
        self, script_urls: List[str], class_names: List[str]
    ):
        """
        检测 UI 库

        Args:
            script_urls: script URL 列表
            class_names: class 名称列表
        """
        all_urls_text = " ".join(script_urls)
        all_classes_text = " ".join(class_names)

        for name, rules in self.UI_LIBRARY_PATTERNS.items():
            confidence = 0

            # 检查 URL 模式
            for pattern in rules["patterns"]:
                if re.search(pattern, all_urls_text, re.IGNORECASE):
                    confidence += 40

            # 检查 class 名称
            matched_classes = 0
            for class_pattern in rules["classes"]:
                if class_pattern in all_classes_text:
                    matched_classes += 1
                    confidence += 15

            if confidence >= 50:
                self.detected_ui_libraries.append(
                    DependencyInfo(
                        name=name,
                        type="library",
                        confidence=min(confidence, 100),
                    )
                )

    async def _detect_utilities(
        self, script_urls: List[str], global_vars: List[str]
    ):
        """
        检测工具库

        Args:
            script_urls: script URL 列表
            global_vars: 全局变量列表
        """
        all_urls_text = " ".join(script_urls)

        for name, rules in self.UTILITY_PATTERNS.items():
            confidence = 0

            # 检查 URL 模式
            for pattern in rules["patterns"]:
                if re.search(pattern, all_urls_text, re.IGNORECASE):
                    confidence += 40

            # 检查全局变量
            for var in rules["global_vars"]:
                if var in global_vars:
                    confidence += 35

            if confidence >= 50:
                self.detected_utilities.append(
                    DependencyInfo(
                        name=name,
                        type="library",
                        confidence=min(confidence, 100),
                    )
                )

    async def _detect_build_tools(self, script_urls: List[str], html: str):
        """
        检测构建工具

        Args:
            script_urls: script URL 列表
            html: HTML 内容
        """
        all_text = " ".join(script_urls) + " " + html

        for name, rules in self.BUILD_TOOL_PATTERNS.items():
            confidence = 0

            for pattern in rules["patterns"]:
                if re.search(pattern, all_text, re.IGNORECASE):
                    confidence += 60

            if confidence >= 50:
                self.detected_build_tools.append(
                    DependencyInfo(
                        name=name,
                        type="tool",
                        confidence=min(confidence, 100),
                    )
                )

    async def _detect_styling(
        self, script_urls: List[str], class_names: List[str]
    ) -> Dict[str, Optional[str]]:
        """
        检测样式方案

        Args:
            script_urls: script URL 列表
            class_names: class 名称列表

        Returns:
            Dict: 样式方案信息
        """
        styling = {
            "preprocessor": None,
            "framework": None,
            "css_in_js": None,
        }

        # 检测 CSS 框架
        if any("tailwind" in cls.lower() for cls in class_names):
            styling["framework"] = "Tailwind CSS"
        elif any("bootstrap" in cls.lower() for cls in class_names):
            styling["framework"] = "Bootstrap"
        elif any("bulma" in cls.lower() for cls in class_names):
            styling["framework"] = "Bulma"

        # 检测 CSS-in-JS
        all_urls = " ".join(script_urls)
        if "styled-components" in all_urls:
            styling["css_in_js"] = "styled-components"
        elif "emotion" in all_urls:
            styling["css_in_js"] = "emotion"
        elif "@mui" in all_urls or "material-ui" in all_urls:
            styling["css_in_js"] = "Material-UI"

        return styling

    async def _extract_meta_tags(self):
        """
        提取 Meta 标签信息
        """
        try:
            meta_tags = await self.page.evaluate("""
                () => {
                    const metas = {};
                    document.querySelectorAll('meta').forEach(meta => {
                        const name = meta.getAttribute('name') || meta.getAttribute('property');
                        const content = meta.getAttribute('content');
                        if (name && content) {
                            metas[name] = content;
                        }
                    });
                    return metas;
                }
            """)
            self.meta_tags = meta_tags or {}
        except:
            self.meta_tags = {}

    async def _detect_features(self):
        """
        检测技术特征
        """
        # 检测 Service Worker
        try:
            has_sw = await self.page.evaluate(
                "() => 'serviceWorker' in navigator"
            )
            if has_sw:
                self.features.add("Service Worker")
        except:
            pass

        # 检测 PWA
        if "theme-color" in self.meta_tags or "apple-mobile-web-app" in str(
            self.meta_tags
        ):
            self.features.add("PWA")

        # 检测 SPA
        if any(f.name in ["React", "Vue", "Angular"] for f in self.detected_frameworks):
            self.features.add("Single Page Application")

        # 检测响应式设计
        if "viewport" in self.meta_tags:
            self.features.add("Responsive Design")
