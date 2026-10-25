import json, os, unittest
from unittest.mock import patch, MagicMock
import publish_drafts

class PublishingTests(unittest.TestCase):
    def test_rejects_formal_backend(self):
        with patch.dict(os.environ,{'CMS_PAYLOAD':json.dumps({'repository':{'ref':'main'}})}),patch.object(publish_drafts,'git') as git:
            with self.assertRaises(ValueError):publish_drafts.run()
            git.assert_not_called()
    def test_unbuilt_draft_cannot_publish(self):
        response=MagicMock();response.__enter__.return_value.read.return_value=b'{"draftSha":"older"}'
        with patch.dict(os.environ,{'CMS_PAYLOAD':json.dumps({'repository':{'ref':'drafts'}})}),patch.object(publish_drafts,'git',return_value='latest') as git,patch.object(publish_drafts,'urlopen',return_value=response):
            with self.assertRaises(ValueError):publish_drafts.run()
            self.assertFalse(any(x.args[0] in ('push','merge') for x in git.call_args_list))
    def test_publish_merges_exact_reviewed_revision_then_dispatches_build(self):
        manifest=MagicMock();manifest.__enter__.return_value.read.return_value=b'{"draftSha":"reviewed"}'
        dispatch=MagicMock();dispatch.__enter__.return_value.status=204
        with patch.dict(os.environ,{'CMS_PAYLOAD':json.dumps({'repository':{'ref':'drafts'}}),'GH_TOKEN':'test-token'}),patch.object(publish_drafts,'git',return_value='reviewed') as git,patch.object(publish_drafts,'urlopen',side_effect=[manifest,dispatch]) as url:
            publish_drafts.run()
            self.assertIn(unittest.mock.call('merge','--no-ff','--no-edit','reviewed'),git.call_args_list)
            self.assertIn(unittest.mock.call('push','origin','HEAD:main'),git.call_args_list)
            request=url.call_args_list[-1].args[0]
            self.assertEqual(request.method,'POST')
            self.assertEqual(json.loads(request.data),{'ref':'main'})

if __name__=='__main__':unittest.main()
