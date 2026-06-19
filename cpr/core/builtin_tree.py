SDKMAN_TREE = {
    "nodes": [
        {
            "id": "sdk",
            "tokens": ["sdk"],
            "title": {"zh-CN": "SDKMAN", "en-US": "SDKMAN"},
            "desc": {"zh-CN": "SDKMAN 命令入口", "en-US": "SDKMAN command root"},
            "children": ["sdk.list", "sdk.install", "sdk.use", "sdk.default", "sdk.current"],
        },
        {
            "id": "sdk.list",
            "tokens": ["sdk", "list"],
            "title": {"zh-CN": "列出候选", "en-US": "List candidates"},
            "children": ["sdk.list.java"],
        },
        {"id": "sdk.list.java", "tokens": ["sdk", "list", "java"], "title": {"zh-CN": "列出 Java", "en-US": "List Java"}, "execute": True},
        {"id": "sdk.install", "tokens": ["sdk", "install"], "title": {"zh-CN": "安装", "en-US": "Install"}, "children": ["sdk.install.java"]},
        {"id": "sdk.install.java", "tokens": ["sdk", "install", "java"], "title": {"zh-CN": "安装 Java", "en-US": "Install Java"}, "children": ["sdk.install.java.{identifier}"]},
        {"id": "sdk.install.java.{identifier}", "tokens": ["sdk", "install", "java", "{identifier}"], "title": {"zh-CN": "Java Identifier", "en-US": "Java Identifier"}, "param": {"source": "sdk.candidates.java.identifiers"}, "execute": True},
        {"id": "sdk.use", "tokens": ["sdk", "use"], "title": {"zh-CN": "使用", "en-US": "Use"}, "children": ["sdk.use.java"]},
        {"id": "sdk.use.java", "tokens": ["sdk", "use", "java"], "title": {"zh-CN": "使用 Java", "en-US": "Use Java"}, "children": ["sdk.use.java.{version}"]},
        {"id": "sdk.use.java.{version}", "tokens": ["sdk", "use", "java", "{version}"], "title": {"zh-CN": "Java 版本", "en-US": "Java version"}, "param": {"source": "sdk.installed.java.versions"}, "execute": True},
        {"id": "sdk.default", "tokens": ["sdk", "default"], "title": {"zh-CN": "默认", "en-US": "Default"}, "children": ["sdk.default.java"]},
        {"id": "sdk.default.java", "tokens": ["sdk", "default", "java"], "title": {"zh-CN": "默认 Java", "en-US": "Default Java"}, "children": ["sdk.default.java.{version}"]},
        {"id": "sdk.default.java.{version}", "tokens": ["sdk", "default", "java", "{version}"], "title": {"zh-CN": "Java 版本", "en-US": "Java version"}, "param": {"source": "sdk.installed.java.versions"}, "execute": True},
        {"id": "sdk.current", "tokens": ["sdk", "current"], "title": {"zh-CN": "当前版本", "en-US": "Current versions"}, "children": ["sdk.current.java"], "execute": True},
        {"id": "sdk.current.java", "tokens": ["sdk", "current", "java"], "title": {"zh-CN": "当前 Java", "en-US": "Current Java"}, "execute": True},
    ]
}
