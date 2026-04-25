import { refractor } from 'refractor/core';
import bash from 'refractor/bash';
import c from 'refractor/c';
import cpp from 'refractor/cpp';
import docker from 'refractor/docker';
import css from 'refractor/css';
import go from 'refractor/go';
import graphql from 'refractor/graphql';
import hcl from 'refractor/hcl';
import html from 'refractor/markup';
import ini from 'refractor/ini';
import java from 'refractor/java';
import javascript from 'refractor/javascript';
import json from 'refractor/json';
import jsx from 'refractor/jsx';
import kotlin from 'refractor/kotlin';
import makefile from 'refractor/makefile';
import markdown from 'refractor/markdown';
import python from 'refractor/python';
import ruby from 'refractor/ruby';
import rust from 'refractor/rust';
import scala from 'refractor/scala';
import sql from 'refractor/sql';
import swift from 'refractor/swift';
import toml from 'refractor/toml';
import tsx from 'refractor/tsx';
import typescript from 'refractor/typescript';
import yaml from 'refractor/yaml';

refractor.register(bash);
refractor.register(c);
refractor.register(cpp);
refractor.register(css);
refractor.register(docker);
refractor.register(go);
refractor.register(graphql);
refractor.register(hcl);
refractor.register(html);
refractor.register(ini);
refractor.register(java);
refractor.register(javascript);
refractor.register(json);
refractor.register(jsx);
refractor.register(kotlin);
refractor.register(makefile);
refractor.register(markdown);
refractor.register(python);
refractor.register(ruby);
refractor.register(rust);
refractor.register(scala);
refractor.register(sql);
refractor.register(swift);
refractor.register(toml);
refractor.register(tsx);
refractor.register(typescript);
refractor.register(yaml);

// react-diff-view's tokenize expects refractor.highlight() to return
// an array of nodes (refractor v2/v3 format), but refractor v5 returns
// a root object {type: 'root', children: [...]}. Wrap highlight to
// unwrap the root and return just the children array.
const wrappedRefractor = {
  ...refractor,
  highlight(code: string, language: string) {
    const result = refractor.highlight(code, language);
    return result.children;
  },
};

export { wrappedRefractor as refractor };
